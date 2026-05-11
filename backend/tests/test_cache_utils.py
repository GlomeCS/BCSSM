import pytest
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend.cache_utils import cached_result, get_ttl_registry


def _make_cache():
    c = MagicMock()
    c.get.return_value = None
    c.set.return_value = True
    return c


# ─── cached_result: basic caching ────────────────────────────────────────────

def test_cache_miss_calls_function_and_stores_result():
    fake_cache = _make_cache()

    @cached_result('key:test', 300, cache=fake_cache)
    def fn():
        return [1, 2, 3]

    result = fn()
    assert result == [1, 2, 3]
    fake_cache.get.assert_called_once_with('key:test')
    fake_cache.set.assert_called_once_with('key:test', [1, 2, 3], timeout=300)


def test_cache_hit_returns_cached_value_without_calling_function():
    fake_cache = _make_cache()
    fake_cache.get.return_value = 'cached'
    calls = []

    @cached_result('key:test', 300, cache=fake_cache)
    def fn():
        calls.append(1)
        return 'fresh'

    result = fn()
    assert result == 'cached'
    assert calls == []
    fake_cache.set.assert_not_called()


def test_dynamic_key_fn_receives_function_args():
    fake_cache = _make_cache()

    @cached_result(lambda x: f'key:{x}', 60, cache=fake_cache)
    def fn(x):
        return x * 2

    fn('hello')
    fake_cache.get.assert_called_once_with('key:hello')
    fake_cache.set.assert_called_once_with('key:hello', 'hellohello', timeout=60)


# ─── error handling: on_error=_RAISE (default) ───────────────────────────────

def test_default_on_error_reraises_sqlalchemy_error():
    fake_cache = _make_cache()

    @cached_result('key:err', 300, cache=fake_cache)
    def fn():
        raise SQLAlchemyError("db down")

    with pytest.raises(SQLAlchemyError):
        fn()
    fake_cache.set.assert_not_called()


# ─── error handling: on_error with error_ttl ─────────────────────────────────

def test_on_error_value_returned_and_cached():
    fake_cache = _make_cache()

    @cached_result('key:err', 300, error_ttl=60, on_error=[], cache=fake_cache)
    def fn():
        raise SQLAlchemyError("oops")

    result = fn()
    assert result == []
    fake_cache.set.assert_called_once_with('key:err', [], timeout=60)


def test_on_error_callable_receives_exception():
    fake_cache = _make_cache()

    @cached_result('key:err', 300, error_ttl=60,
                   on_error=lambda e: {"error": str(e)}, cache=fake_cache)
    def fn():
        raise SQLAlchemyError("msg")

    result = fn()
    assert "msg" in result["error"]
    fake_cache.set.assert_called_once()


def test_on_error_without_error_ttl_returns_fallback_but_does_not_cache():
    fake_cache = _make_cache()

    @cached_result('key:err', 300, on_error=[], cache=fake_cache)
    def fn():
        raise SQLAlchemyError("oops")

    result = fn()
    assert result == []
    fake_cache.set.assert_not_called()


# ─── TTL registry ─────────────────────────────────────────────────────────────

def test_ttl_registry_records_decorated_functions():
    fake_cache = _make_cache()

    @cached_result('key:reg', 999, cache=fake_cache)
    def my_registered_fn():
        return None

    registry = get_ttl_registry()
    assert 'my_registered_fn' in registry
    assert registry['my_registered_fn'] == 999
