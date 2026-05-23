import copy
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

_RAISE = object()
_ttl_registry = {}


def get_ttl_registry():
    return dict(_ttl_registry)


def cached_result(key_fn, ttl, error_ttl=None, on_error=_RAISE, cache=None):
    """
    key_fn: str for static keys, or callable(*args, **kwargs) -> str for dynamic keys
    ttl: success cache TTL (seconds)
    error_ttl: error cache TTL (seconds); None = don't cache on error
    on_error: value or callable(exc)->value returned on SQLAlchemyError;
              default _RAISE re-raises the exception
    cache: injectable cache instance for testing; defaults to backend.globals.cache
    """
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
                fallback = on_error(e) if callable(on_error) else copy.copy(on_error)
                if error_ttl is not None:
                    try:
                        _cache.set(key, fallback, timeout=error_ttl)
                    except Exception as cache_error:
                        logger.warning("Cache write failed for %s: %s", key, cache_error)
                return fallback

        return wrapper
    return decorator
