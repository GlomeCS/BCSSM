import copy
from dataclasses import dataclass, field
from functools import wraps
from typing import Any
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

_RAISE = object()
_ttl_registry = {}


def get_ttl_registry():
    return dict(_ttl_registry)


@dataclass
class CacheEntry:
    ttl: int
    group: str
    error_ttl: int | None = None
    on_error: Any = field(default_factory=lambda: _RAISE)


# Single source of truth for cache key templates, TTLs, and invalidation groups.
# Used by cached_result (TTL lookup) and clear_group (bulk invalidation in #165).
CACHE_REGISTRY: dict[str, CacheEntry] = {
    "users:all:list":                    CacheEntry(ttl=900,  group="users",    on_error=[]),
    "user:duty:{name}:{date}":           CacheEntry(ttl=600,  group="duties"),
    "duties:today:{day}:{cycle}:{name}": CacheEntry(ttl=1800, group="duties",   error_ttl=60, on_error=[]),
    "duties:schedule:14day:{date}":      CacheEntry(ttl=7200, group="duties",   error_ttl=60, on_error=[]),
    "sections:all:list":                 CacheEntry(ttl=3600, group="sections", error_ttl=60),
    "users:section:{name}":              CacheEntry(ttl=1800, group="users",    error_ttl=60),
    "users:section:{name}:detailed":     CacheEntry(ttl=1800, group="users",    error_ttl=60),
    "feedback:dates:all":                CacheEntry(ttl=7200, group="feedback", error_ttl=60),
    "sections:with_users:all_v6":        CacheEntry(ttl=1800, group="sections", error_ttl=60),
    "sections:statistics:summary":       CacheEntry(ttl=3600, group="sections", error_ttl=60),
}


def cached_result(key_fn, ttl=None, error_ttl=None, on_error=_RAISE, cache=None,
                  registry_key=None):
    """
    key_fn: str for static keys, or callable(*args, **kwargs) -> str for dynamic keys
    ttl: success cache TTL (seconds); if None, looked up from CACHE_REGISTRY
    error_ttl: error cache TTL (seconds); if None, looked up from CACHE_REGISTRY
    on_error: value or callable(exc)->value returned on SQLAlchemyError;
              default _RAISE re-raises the exception
    cache: injectable cache instance for testing; defaults to backend.globals.cache
    registry_key: CACHE_REGISTRY template to use for TTL lookup when key_fn is callable
    """
    # Resolve TTL and error_ttl from registry when not explicitly provided
    _registry_key = registry_key if registry_key is not None else (
        key_fn if isinstance(key_fn, str) else None
    )
    if _registry_key is not None:
        entry = CACHE_REGISTRY.get(_registry_key)
        if entry is not None:
            if ttl is None:
                ttl = entry.ttl
            if error_ttl is None:
                error_ttl = entry.error_ttl
            if on_error is _RAISE and entry.on_error is not _RAISE:
                on_error = entry.on_error

    if ttl is None:
        raise ValueError(
            f"No TTL found for '{_registry_key}' — add it to CACHE_REGISTRY or pass ttl= explicitly"
        )

    def decorator(func):
        _ttl_registry[func.__name__] = ttl

        @wraps(func)
        def wrapper(*args, **kwargs):
            if cache is not None:
                _cache = cache
            else:
                from backend.globals import cache as _global_cache
                _cache = _global_cache

            key = key_fn(*args, **kwargs) if callable(key_fn) else key_fn

            try:
                hit = _cache.get(key)
            except Exception as e:
                logger.warning("Cache read failed for %s: %s", key, e)
                hit = None
            if hit is not None:
                logger.info("Cache hit: %s", key)
                return hit

            try:
                result = func(*args, **kwargs)
                try:
                    _cache.set(key, result, timeout=ttl)
                except Exception as e:
                    logger.warning("Cache write failed for %s: %s", key, e)
                return result
            except SQLAlchemyError as e:
                logger.error("Query failed, cache key %s: %s", key, e)
                if on_error is _RAISE:
                    raise
                fallback = on_error(e) if callable(on_error) else copy.deepcopy(on_error)
                if error_ttl is not None:
                    try:
                        _cache.set(key, fallback, timeout=error_ttl)
                    except Exception as cache_error:
                        logger.warning("Cache write failed for %s: %s", key, cache_error)
                return fallback

        return wrapper
    return decorator


def _template_to_glob(template: str) -> str:
    """Convert 'foo:{bar}:{baz}' to 'foo:*' for Redis SCAN pattern matching."""
    idx = template.find('{')
    return template[:idx] + '*' if idx != -1 else template


def _scan_delete(cache_instance, pattern: str) -> int:
    """Delete all Redis keys matching a glob pattern via SCAN."""
    redis_client = getattr(
        getattr(cache_instance, 'cache', None), '_write_client', None
    )
    if redis_client is None:
        logger.debug(
            "Redis client not accessible; skipping pattern delete for %s",
            pattern,
        )
        return 0
    try:
        keys = list(redis_client.scan_iter(match=pattern, count=100))
        if keys:
            redis_client.delete(*keys)
        return len(keys)
    except Exception as e:
        logger.warning("Pattern delete failed for %s: %s", pattern, e)
        return 0


def clear_group(group_name: str, cache=None) -> None:
    """Delete all cached keys belonging to group_name.

    Static keys are deleted directly. Template keys (containing {}) are
    converted to glob patterns and deleted via Redis SCAN.
    """
    if cache is None:
        from backend.globals import cache as _global_cache
        cache = _global_cache

    static_keys: list[str] = []
    glob_patterns: set[str] = set()

    for template, entry in CACHE_REGISTRY.items():
        if entry.group != group_name:
            continue
        if '{' not in template:
            static_keys.append(template)
        else:
            glob_patterns.add(_template_to_glob(template))

    try:
        for key in static_keys:
            cache.delete(key)
        for pattern in glob_patterns:
            _scan_delete(cache, pattern)
    except Exception as e:
        logger.warning(
            "clear_group(%s) encountered an error: %s", group_name, e
        )

    logger.info(
        "Cleared cache group '%s': %d static key(s), %d pattern(s)",
        group_name, len(static_keys), len(glob_patterns),
    )
