import logging
import os
import urllib.parse

from redis.exceptions import RedisError

from backend.globals import cache
from backend.bcssm_backend.cache_utils import get_ttl_registry
from backend.bcssm_backend.exceptions import CacheError

logger = logging.getLogger(__name__)


def _fmt_ttl(ttl: int) -> str:
    if ttl >= 3600:
        hours = ttl // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if ttl >= 60:
        minutes = ttl // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{ttl} second{'s' if ttl != 1 else ''}"


def _redact_redis_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 6379
    return f"{host}:{port}"


def get_cache_status() -> dict:
    test_key = 'status:test'
    try:
        cache.set(test_key, 'working', timeout=10)
        test_result = cache.get(test_key)
        cache.delete(test_key)
    except Exception as e:
        raise CacheError(f"Cache probe failed: {e}") from e
    return {
        "status": "healthy" if test_result == 'working' else "unhealthy",
        "redis_url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379')),
        "default_timeout": 300,
        "test_result": test_result,
        "cache_type": "RedisCache",
        "available_operations": {
            "clear_users": "/api/admin/cache/clear (POST with type: users)",
            "clear_duties": "/api/admin/cache/clear (POST with type: duties)",
            "clear_feedback": "/api/admin/cache/clear (POST with type: feedback)",
            "clear_all": "/api/admin/cache/clear (POST with type: all)"
        }
    }


def get_cache_info() -> dict:
    return {
        "cache_config": {
            "type": "RedisCache",
            "url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379')),
            "default_timeout": 300
        },
        "cached_functions": {
            name: _fmt_ttl(ttl) for name, ttl in get_ttl_registry().items()
        },
        "management_endpoints": {
            "status": "GET /api/admin/cache/status",
            "clear": "POST /api/admin/cache/clear",
            "info": "GET /api/admin/cache/info"
        }
    }


def get_health_status() -> dict:
    try:
        cache.set('health:test', 'ok', timeout=10)
        cache_ok = cache.get('health:test') == 'ok'
        cache.delete('health:test')
    except RedisError as e:
        logger.warning("Cache probe failed: %s", e)
        cache_ok = False
    health = {
        "status": "healthy",
        "database": "connected",
        "cache": "healthy" if cache_ok else "unhealthy",
        "environment": os.getenv('FLASK_ENV', 'development'),
        "redis_url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
    }
    if not cache_ok:
        health["status"] = "degraded"
    return health
