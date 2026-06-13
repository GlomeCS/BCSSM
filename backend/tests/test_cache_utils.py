import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend.cache_utils import (
    cached_result, get_ttl_registry, CACHE_REGISTRY,
    clear_group, _template_to_glob, _scan_delete,
)


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
    def fn():  # pragma: no cover
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


# ─── on_error mutable default isolation ──────────────────────────────────────

def test_on_error_list_returns_independent_copy_each_call():
    fake_cache = _make_cache()

    @cached_result('key:mut', 300, on_error=[], cache=fake_cache)
    def fn():
        raise SQLAlchemyError("oops")

    result1 = fn()
    result1.append('mutation')
    result2 = fn()
    assert result2 == [], "Mutation of first fallback should not affect subsequent calls"


def test_on_error_nested_mutable_returns_independent_copy_each_call():
    fake_cache = _make_cache()

    @cached_result('key:nestedmut', 300, on_error={"data": []}, cache=fake_cache)
    def fn():
        raise SQLAlchemyError("oops")

    result1 = fn()
    result1["data"].append('mutation')
    result2 = fn()
    assert result2["data"] == [], "Mutation of nested list should not affect subsequent calls"


# ─── cache backend failure resilience ────────────────────────────────────────

def test_cache_read_failure_treated_as_miss():
    fake_cache = _make_cache()
    fake_cache.get.side_effect = Exception("Redis down")
    calls = []

    @cached_result('key:test', 300, cache=fake_cache)
    def fn():
        calls.append(1)
        return 'result'

    result = fn()
    assert result == 'result'
    assert calls == [1]


def test_cache_write_failure_still_returns_result():
    fake_cache = _make_cache()
    fake_cache.set.side_effect = Exception("Redis write failed")

    @cached_result('key:test', 300, cache=fake_cache)
    def fn():
        return 'result'

    result = fn()
    assert result == 'result'


def test_cache_error_fallback_write_failure_still_returns_fallback():
    fake_cache = _make_cache()
    fake_cache.set.side_effect = Exception("Redis write failed")

    @cached_result('key:err', 300, error_ttl=60, on_error='fallback', cache=fake_cache)
    def fn():
        raise SQLAlchemyError("db down")

    result = fn()
    assert result == 'fallback'


# ─── TTL registry ─────────────────────────────────────────────────────────────

def test_ttl_registry_records_decorated_functions():
    fake_cache = _make_cache()

    @cached_result('key:reg', 999, cache=fake_cache)
    def my_registered_fn():  # pragma: no cover
        return None

    registry = get_ttl_registry()
    assert 'my_registered_fn' in registry
    assert registry['my_registered_fn'] == 999


# ─── CACHE_REGISTRY ───────────────────────────────────────────────────────────

def test_registry_lookup_sets_ttl_for_static_key():
    fake_cache = _make_cache()

    @cached_result('users:all:list', cache=fake_cache)
    def fn():
        return ['a']

    fn()
    fake_cache.set.assert_called_once_with('users:all:list', ['a'], timeout=900)


def test_registry_lookup_via_registry_key_for_dynamic_key():
    fake_cache = _make_cache()

    @cached_result(lambda name: f'user:duty:{name}:2025-01-01',
                   registry_key='user:duty:{name}:{date}', cache=fake_cache)
    def fn(name):
        return {'user': name}

    fn('Alice')
    _, kwargs = fake_cache.set.call_args
    assert kwargs['timeout'] == 600


def test_registry_missing_key_with_no_explicit_ttl_raises():
    with pytest.raises(ValueError, match="CACHE_REGISTRY"):
        @cached_result(lambda x: f'unknown:{x}', registry_key='unknown:{x}')
        def fn(x):  # pragma: no cover
            return x


def test_all_registry_entries_have_valid_group():
    valid_groups = {"users", "duties", "sections", "feedback"}
    for key, entry in CACHE_REGISTRY.items():
        assert entry.group in valid_groups, (
            f"Registry entry '{key}' has unknown group '{entry.group}'"
        )


def test_all_registry_entries_have_positive_ttl():
    for key, entry in CACHE_REGISTRY.items():
        assert entry.ttl > 0, f"Registry entry '{key}' has non-positive ttl {entry.ttl}"
        if entry.error_ttl is not None:
            assert entry.error_ttl > 0, (
                f"Registry entry '{key}' has non-positive error_ttl {entry.error_ttl}"
            )


# ─── Duty key design ──────────────────────────────────────────────────────────

def test_user_duty_key_is_date_based():
    from backend.bcssm_backend.utils import _user_duty_key
    fixed_date = date(2025, 6, 16)
    with patch('backend.bcssm_backend.utils.datetime') as mock_dt:
        mock_dt.now.return_value.date.return_value = fixed_date
        key = _user_duty_key('Alice')
    assert key == f'user:duty:Alice:{fixed_date}'
    assert 'day' not in key
    assert 'cycle' not in key


# ─── _template_to_glob ─────────────────────────────────────────────────────

def test_template_to_glob_static_key_unchanged():
    assert _template_to_glob('users:all:list') == 'users:all:list'


def test_template_to_glob_single_placeholder():
    assert _template_to_glob('users:section:{name}') == 'users:section:*'


def test_template_to_glob_multiple_placeholders():
    result = _template_to_glob('duties:today:{day}:{cycle}:{name}')
    assert result == 'duties:today:*'


def test_template_to_glob_leading_placeholder():
    assert _template_to_glob('{key}:suffix') == '*'


# ─── _scan_delete ───────────────────────────────────────────────────────────

def test_scan_delete_finds_and_deletes_matching_keys():
    mock_redis = MagicMock()
    found_keys = ['duties:today:3:0:Alice', 'duties:today:4:1:Bob']
    mock_redis.scan_iter.return_value = found_keys
    fake_cache = MagicMock()
    fake_cache.cache._write_client = mock_redis

    count = _scan_delete(fake_cache, 'duties:today:*')

    mock_redis.scan_iter.assert_called_once_with(
        match='duties:today:*', count=100
    )
    mock_redis.delete.assert_called_once_with(*found_keys)
    assert count == 2


def test_scan_delete_no_keys_found_skips_delete():
    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = []
    fake_cache = MagicMock()
    fake_cache.cache._write_client = mock_redis

    count = _scan_delete(fake_cache, 'duties:today:*')

    mock_redis.delete.assert_not_called()
    assert count == 0


def test_scan_delete_returns_zero_when_no_redis_client():
    fake_cache = MagicMock(spec=[])  # no attributes → _write_client is None
    count = _scan_delete(fake_cache, 'duties:*')
    assert count == 0


def test_scan_delete_swallows_exception_and_returns_zero():
    mock_redis = MagicMock()
    mock_redis.scan_iter.side_effect = Exception("connection refused")
    fake_cache = MagicMock()
    fake_cache.cache._write_client = mock_redis

    count = _scan_delete(fake_cache, 'duties:*')
    assert count == 0


# ─── clear_group ────────────────────────────────────────────────────────────

def _make_cache_with_redis():
    """Return a (fake_cache, mock_redis) pair with _write_client wired up."""
    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = []
    fake_cache = MagicMock()
    fake_cache.cache._write_client = mock_redis
    return fake_cache, mock_redis


def test_clear_group_feedback_deletes_static_key():
    fake_cache, _ = _make_cache_with_redis()
    clear_group("feedback", cache=fake_cache)
    fake_cache.delete.assert_called_once_with("feedback:dates:all")


def test_clear_group_sections_deletes_all_static_keys():
    fake_cache, _ = _make_cache_with_redis()
    clear_group("sections", cache=fake_cache)

    deleted = {c.args[0] for c in fake_cache.delete.call_args_list}
    assert "sections:all:list" in deleted
    assert "sections:with_users:all_v6" in deleted
    assert "sections:statistics:summary" in deleted


def test_clear_group_users_deletes_static_and_scans_dynamic(caplog):
    fake_cache, mock_redis = _make_cache_with_redis()
    clear_group("users", cache=fake_cache)

    fake_cache.delete.assert_called_with("users:all:list")

    patterns_scanned = {
        c.kwargs.get('match') or c.args[0]
        for c in mock_redis.scan_iter.call_args_list
    }
    assert "users:section:*" in patterns_scanned


def test_clear_group_duties_scans_all_three_patterns():
    fake_cache, mock_redis = _make_cache_with_redis()
    clear_group("duties", cache=fake_cache)

    fake_cache.delete.assert_not_called()

    patterns_scanned = {
        c.kwargs.get('match') or c.args[0]
        for c in mock_redis.scan_iter.call_args_list
    }
    assert "user:duty:*" in patterns_scanned
    assert "duties:today:*" in patterns_scanned
    assert "duties:schedule:14day:*" in patterns_scanned


def test_clear_group_unknown_group_is_noop():
    fake_cache, mock_redis = _make_cache_with_redis()
    clear_group("nonexistent", cache=fake_cache)
    fake_cache.delete.assert_not_called()
    mock_redis.scan_iter.assert_not_called()


def test_clear_group_deletes_found_dynamic_keys():
    fake_cache, mock_redis = _make_cache_with_redis()
    mock_redis.scan_iter.return_value = ['feedback:dates:all']

    clear_group("feedback", cache=fake_cache)

    fake_cache.delete.assert_called_with("feedback:dates:all")


def test_clear_group_scan_deletes_found_keys():
    mock_redis = MagicMock()
    mock_redis.scan_iter.side_effect = [
        ['user:duty:Alice:2026-01-01'],
        ['duties:today:3:0:Alice'],
        ['duties:schedule:14day:2026-01-01'],
    ]
    fake_cache = MagicMock()
    fake_cache.cache._write_client = mock_redis

    clear_group("duties", cache=fake_cache)

    assert mock_redis.delete.call_count == 3
    deleted_keys = {c.args[0] for c in mock_redis.delete.call_args_list}
    assert 'user:duty:Alice:2026-01-01' in deleted_keys
    assert 'duties:today:3:0:Alice' in deleted_keys
    assert 'duties:schedule:14day:2026-01-01' in deleted_keys


def test_clear_group_logs_cleared_group(caplog):
    import logging
    fake_cache, _ = _make_cache_with_redis()
    with caplog.at_level(logging.INFO, logger='backend.bcssm_backend.cache_utils'):  # noqa: E501
        clear_group("feedback", cache=fake_cache)
    assert "feedback" in caplog.text


def test_clear_group_exception_is_swallowed():
    fake_cache = MagicMock()
    fake_cache.delete.side_effect = Exception("Redis down")
    clear_group("feedback", cache=fake_cache)  # must not raise


# ─── clear_* wrappers in utils use clear_group ───────────────────────────────

def test_clear_duty_cache_delegates_to_clear_group(monkeypatch):
    calls = []
    monkeypatch.setattr(
        'backend.bcssm_backend.utils.clear_group',
        lambda group, **kw: calls.append(group),
    )
    from backend.bcssm_backend import utils
    utils.clear_duty_cache()
    assert calls == ["duties"]


def test_clear_feedback_cache_delegates_to_clear_group(monkeypatch):
    calls = []
    monkeypatch.setattr(
        'backend.bcssm_backend.utils.clear_group',
        lambda group, **kw: calls.append(group),
    )
    from backend.bcssm_backend import utils
    utils.clear_feedback_cache()
    assert calls == ["feedback"]


def test_clear_user_cache_delegates_to_both_groups(monkeypatch):
    calls = []
    monkeypatch.setattr(
        'backend.bcssm_backend.utils.clear_group',
        lambda group, **kw: calls.append(group),
    )
    from backend.bcssm_backend import utils
    utils.clear_user_cache()
    assert set(calls) == {"users", "sections"}
