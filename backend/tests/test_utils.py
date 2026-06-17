import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from datetime import datetime
import logging
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from backend.bcssm_backend import create_app
from backend.bcssm_backend import duty_queries, user_queries, section_queries
from backend.bcssm_backend import feedback_queries, auth_queries, cache_utils
from backend.bcssm_backend.db import execute_readonly_query as _real_execute_readonly_query
from backend.bcssm_backend.db import execute_query as _real_execute_query
from backend.bcssm_backend.exceptions import ValidationError, AuthenticationError

# ─── 0) Autouse fixture to push a Flask app context ─────────────────────────
@pytest.fixture(autouse=True)
def flask_app_context(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'testing')
    app = create_app()
    ctx = app.app_context()
    ctx.push()
    yield
    ctx.pop()

# ─── 1) Autouse fixture to stub read-only helper ────────────────────────────
@pytest.fixture(autouse=True)
def mock_readonly(mocker):
    return mocker.patch('backend.bcssm_backend.db.execute_readonly_query')

# ─── 1.5) Mock the cache to avoid Redis connection issues ───────────────────
@pytest.fixture(autouse=True)
def mock_cache(monkeypatch):
    fake_cache = MagicMock()
    fake_cache.get.return_value = None
    fake_cache.set.return_value = True
    fake_cache.delete.return_value = True
    fake_cache.clear.return_value = True

    monkeypatch.setattr('backend.globals.cache', fake_cache)
    monkeypatch.setattr('backend.bcssm_backend.auth_queries.cache', fake_cache)
    return fake_cache

# ─── 2) Fixture to mock db.session directly (for testing execute_query) ─────
@pytest.fixture
def mock_db_session():
    with patch('backend.bcssm_backend.db.db.session') as sess:
        sess.begin.return_value.__enter__.return_value = sess
        sess.begin.return_value.__exit__.return_value = None
        yield sess

# ─── 3) Utility to control "today" in date-sensitive code ─────────────────────
_FAKE_DATE = datetime(2025, 6, 16).date()

class FakeDatetime:
    today_date = _FAKE_DATE

    @classmethod
    def now(cls):
        return SimpleNamespace(
            weekday=lambda: cls.today_weekday,
            date=lambda: cls.today_date,
        )

# ─── 4) Tests for get_all_users() ────────────────────────────────────────────
def test_get_all_users_happy_path(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('Alice Smith','SectionA','RoleA','TeamA'),
        ('Bob Jones','SectionB','RoleB','TeamB'),
    ]
    result = user_queries.get_all_users()
    assert result == ['Alice Smith','Bob Jones']

    mock_cache.get.assert_called_once_with('users:all:list')
    mock_cache.set.assert_called_once_with('users:all:list', ['Alice Smith','Bob Jones'], timeout=900)

    sql = mock_readonly.call_args[0][0]
    expected_sql = """
    SELECT
        u.name,
        COALESCE(s.name, 'Unassigned') AS section,
        u.role,
        COALESCE(dt.name, 'No Team') AS team
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id
    ORDER BY
        CASE
            WHEN POSITION(' ' IN u.name) > 0
            THEN SUBSTRING(u.name FROM POSITION(' ' IN u.name) + 1)
            ELSE u.name
        END,
        u.name;
    """
    assert sql.strip() == expected_sql.strip()

def test_get_all_users_cache_hit(mock_readonly, mock_cache):
    mock_cache.get.return_value = ['Cached Alice', 'Cached Bob']

    result = user_queries.get_all_users()

    assert result == ['Cached Alice', 'Cached Bob']
    mock_cache.get.assert_called_once_with('users:all:list')
    mock_readonly.assert_not_called()
    mock_cache.set.assert_not_called()

def test_get_all_users_db_failure_returns_empty_list(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("DB is down")
    result = user_queries.get_all_users()
    assert result == []
    assert isinstance(result, list)

# ─── 5) Tests for get_user_duty() ─────────────────────────────────────────────
def test_get_user_duty_valid_today_returns_expected(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 2
    monkeypatch.setattr(duty_queries, 'datetime', FakeDatetime)
    monkeypatch.setattr(duty_queries, 'get_current_cycle_week', lambda: 0)

    mock_readonly.return_value = [
        ("Ivy","Minis","Team Member","Team1","Lunch Duty")
    ]
    result = duty_queries.get_user_duty("Ivy")
    assert result == {
        "user": "Ivy",
        "section": "Minis",
        "role": "Team Member",
        "team": "Team1",
        "duty": "Lunch Duty"
    }

    cache_key_pattern = f'user:duty:Ivy:{_FAKE_DATE}'
    mock_cache.get.assert_called_once_with(cache_key_pattern)
    mock_cache.set.assert_called_once()
    cache_set_args = mock_cache.set.call_args
    assert cache_set_args[0][0] == cache_key_pattern
    assert cache_set_args[1]['timeout'] == 600

    mock_readonly.assert_called_once()
    sql, params = mock_readonly.call_args[0]
    assert isinstance(params['day'], int)
    assert params['day'] == 3
    assert params['cycle_week'] == 0

def test_get_user_duty_cache_hit(monkeypatch, mock_readonly, mock_cache):
    cached_duty = {
        "user": "Ivy",
        "section": "Minis",
        "role": "Team Member",
        "team": "Team1",
        "duty": "Cached Duty"
    }
    mock_cache.get.return_value = cached_duty

    FakeDatetime.today_weekday = 2
    monkeypatch.setattr(duty_queries, 'datetime', FakeDatetime)
    monkeypatch.setattr(duty_queries, 'get_current_cycle_week', lambda: 0)

    result = duty_queries.get_user_duty("Ivy")

    assert result == cached_duty
    mock_cache.get.assert_called_once_with(f'user:duty:Ivy:{_FAKE_DATE}')
    mock_readonly.assert_not_called()
    mock_cache.set.assert_not_called()

def test_get_user_duty_not_assigned_returns_error(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 0
    monkeypatch.setattr(duty_queries, 'datetime', FakeDatetime)
    monkeypatch.setattr(duty_queries, 'get_current_cycle_week', lambda: 0)

    mock_readonly.return_value = []
    result = duty_queries.get_user_duty("NoOne")
    assert isinstance(result, dict)
    assert "error" in result
    assert "not found or no duty" in result["error"].lower()

    mock_cache.set.assert_called_once()
    cache_set_args = mock_cache.set.call_args
    assert cache_set_args[1]['timeout'] == 600

def test_get_user_duty_exception_propagates_error(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 0
    monkeypatch.setattr(duty_queries, 'datetime', FakeDatetime)
    monkeypatch.setattr(duty_queries, 'get_current_cycle_week', lambda: 0)

    mock_readonly.side_effect = SQLAlchemyError("Something broke")
    with pytest.raises(SQLAlchemyError, match="Something broke"):
        duty_queries.get_user_duty("SomeUser")

    mock_cache.set.assert_not_called()

def test_get_user_duty_short_row(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 0
    monkeypatch.setattr(duty_queries, 'datetime', FakeDatetime)
    monkeypatch.setattr(duty_queries, 'get_current_cycle_week', lambda: 0)

    mock_readonly.return_value = [('Alice', 'Section1', 'Role1')]
    result = duty_queries.get_user_duty("Alice")
    assert isinstance(result, dict)
    assert "error" in result
    assert "Unexpected data format" in result["error"]

def test_execute_readonly_query_db_error():
    from backend.bcssm_backend.exceptions import DatabaseError
    with patch('backend.bcssm_backend.db.db') as mock_db:
        mock_db.engine.connect.side_effect = SQLAlchemyError("connection failed")
        with pytest.raises(DatabaseError, match="Database error"):
            _real_execute_readonly_query("SELECT 1")


def test_execute_readonly_query_success(caplog):
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("row1",)]
    mock_conn.execute.return_value = mock_result

    with patch('backend.bcssm_backend.db.db') as mock_db:
        mock_db.engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db.engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        with caplog.at_level(logging.INFO, logger="backend.bcssm_backend.db"):
            rows = _real_execute_readonly_query("SELECT 1", silent=False)

    assert rows == [("row1",)]
    assert any("Rows fetched" in r.message for r in caplog.records)

# ─── 6) Tests for get_users_by_section() ───────────────────────────────────
def test_get_users_by_section_db_error_returns_error(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("DB error on section query")
    result = section_queries.get_users_by_section("Minis")
    assert isinstance(result, dict)
    assert "Failed to fetch users by section" in result["error"]
    assert "DB error on section query" in result["error"]

# ─── 7) Tests for get_all_sections() ───────────────────────────────────────
def test_get_all_sections_with_records(mock_readonly, mock_cache):
    mock_readonly.return_value = [("Minis",), ("Micros",), ("Majors",)]
    result = section_queries.get_all_sections()
    assert result == ["Minis", "Micros", "Majors"]

    mock_cache.get.assert_called_once_with('sections:all:list')
    mock_cache.set.assert_called_once_with('sections:all:list', ["Minis", "Micros", "Majors"], timeout=3600)

    sql = mock_readonly.call_args[0][0]
    assert "ORDER BY display_order, name" in sql.strip()
    assert sql.strip().startswith("SELECT name")

def test_get_all_sections_no_records(mock_readonly, mock_cache):
    mock_readonly.return_value = []
    result = section_queries.get_all_sections()
    assert result == []

def test_get_all_sections_exception(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("Database failure")
    result = section_queries.get_all_sections()
    assert isinstance(result, dict)
    assert "Failed to fetch sections" in result["error"]
    assert "Database failure" in result["error"]

# ─── 8) Tests for get_all_feedback_dates() ──────────────────────────────────
def test_get_all_feedback_dates_with_records(mock_readonly, mock_cache):
    mock_readonly.return_value = [("2025-06-01",), ("2025-05-25",)]
    result = feedback_queries.get_all_feedback_dates()
    assert result == ["2025-06-01", "2025-05-25"]

    mock_cache.get.assert_called_once_with('feedback:dates:all')
    mock_cache.set.assert_called_once_with('feedback:dates:all', ["2025-06-01", "2025-05-25"], timeout=7200)

    sql = mock_readonly.call_args[0][0]
    expected_sql = """
    SELECT DISTINCT date
    FROM feedback_records
    ORDER BY date DESC;
    """
    assert sql.strip() == expected_sql.strip()

def test_get_all_feedback_dates_no_records(mock_readonly, mock_cache):
    mock_readonly.return_value = []
    result = feedback_queries.get_all_feedback_dates()
    assert result == []

def test_get_all_feedback_dates_exception(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("Database error")
    result = feedback_queries.get_all_feedback_dates()
    assert isinstance(result, dict)
    assert "Failed to fetch feedback dates" in result["error"]
    assert "Database error" in result["error"]

# ─── 9) Tests for execute_query (transactions) ──────────────────────────────
def test_execute_query_success_with_results(mock_db_session):
    mock_result = MagicMock()
    mock_result.returns_rows = True
    mock_result.fetchall.return_value = [("Alice",)]
    mock_db_session.execute.return_value = mock_result

    rows = _real_execute_query("SELECT name FROM users")

    mock_db_session.execute.assert_called_once()
    mock_db_session.begin.assert_called_once()
    assert rows == [("Alice",)]

def test_execute_query_success_no_results(mock_db_session):
    mock_result = MagicMock()
    mock_result.returns_rows = False
    mock_db_session.execute.return_value = mock_result
    rows = _real_execute_query("UPDATE users SET name='X'")
    mock_db_session.execute.assert_called_once()
    mock_db_session.begin.assert_called_once()
    assert rows is None

def test_execute_query_failure_triggers_rollback(mock_db_session):
    mock_db_session.execute.side_effect = SQLAlchemyError("DB error")
    with pytest.raises(Exception, match="Database error"):
        _real_execute_query("DELETE FROM users")
    mock_db_session.rollback.assert_called_once()

# Test get_todays_duties to verify cycle_week usage
def test_get_todays_duties_uses_cycle_week(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 1  # Tuesday
    monkeypatch.setattr(duty_queries, 'datetime', FakeDatetime)
    monkeypatch.setattr(duty_queries, 'get_current_cycle_week', lambda: 1)

    mock_readonly.return_value = [
        (1, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}], True)
    ]

    result = duty_queries.get_todays_duties("Alice")

    cache_key_pattern = 'duties:today:day2:cycle1:userAlice'
    mock_cache.get.assert_called_once_with(cache_key_pattern)
    mock_cache.set.assert_called_once()

    sql, params = mock_readonly.call_args[0]
    assert params['day'] == 2
    assert params['cycle_week'] == 1
    assert params['user_name'] == "Alice"

    assert "WITH computed_cycle" not in sql
    assert "WHERE ds.day = :day" in sql
    assert "AND ds.cycle_week = :cycle_week" in sql

def test_caching_behavior(mock_readonly, mock_cache):
    mock_readonly.return_value = [('Alice Smith','SectionA','RoleA','TeamA')]

    result1 = user_queries.get_all_users()
    assert mock_readonly.call_count == 1
    assert mock_cache.get.call_count == 1
    assert mock_cache.set.call_count == 1

    mock_cache.reset_mock()
    mock_cache.get.return_value = ['Alice Smith']
    mock_readonly.reset_mock()

    result2 = user_queries.get_all_users()

    assert mock_cache.get.call_count == 1
    assert mock_readonly.call_count == 0
    assert mock_cache.set.call_count == 0

    assert result2 == ['Alice Smith']

# Test the get_duty_schedule optimization
def test_get_duty_schedule_uses_parameterized_query(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        (1, 0, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}])
    ]

    result = duty_queries.get_duty_schedule()

    assert isinstance(result, list)
    assert len(result) == 14

    mock_cache.get.assert_called_once()
    cache_key = mock_cache.get.call_args[0][0]
    assert cache_key == 'duties:schedule:14day:anchor'
    mock_cache.set.assert_called_once()

    sql, params = mock_readonly.call_args[0]
    assert "ANY(:days)" in sql
    assert "ANY(:cycles)" in sql
    assert "days" in params
    assert "cycles" in params

    assert isinstance(params['days'], list)
    assert isinstance(params['cycles'], list)

def test_get_current_cycle_week_calculation():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    anchor = duty_queries.CYCLE_ANCHOR.date()

    assert duty_queries._cycle_week_for_date(anchor) == 0
    assert duty_queries._cycle_week_for_date(anchor + timedelta(weeks=1)) == 1
    assert duty_queries._cycle_week_for_date(anchor + timedelta(weeks=2)) == 0

# ─── Tests for cache clearing methods ────────────────────────────────────────

def test_clear_user_cache(mock_cache):
    cache_utils.clear_user_cache()

    deleted_keys = [c.args[0] for c in mock_cache.delete.call_args_list]
    assert 'users:all:list' in deleted_keys
    assert 'sections:all:list' in deleted_keys
    assert 'sections:with_users:all_v6' in deleted_keys

def test_clear_duty_cache(mock_cache):
    with patch('backend.bcssm_backend.cache_utils.clear_group') as mock_cg:
        cache_utils.clear_duty_cache()
        mock_cg.assert_called_once_with("duties")

def test_clear_feedback_cache(mock_cache):
    cache_utils.clear_feedback_cache()
    mock_cache.delete.assert_called_once_with('feedback:dates:all')

def test_clear_all_cache(mock_cache):
    cache_utils.clear_all_cache()
    mock_cache.clear.assert_called_once()
    mock_cache.delete.assert_not_called()

def test_clear_cache_methods_handle_errors_gracefully(mock_cache, caplog):
    mock_cache.delete.side_effect = RedisError("Redis connection failed")
    mock_cache.clear.side_effect = RedisError("Redis connection failed")

    with caplog.at_level(logging.WARNING):
        cache_utils.clear_user_cache()
        cache_utils.clear_feedback_cache()
        cache_utils.clear_all_cache()
        cache_utils.clear_duty_cache()

    assert "Failed to clear all caches" in caplog.text
    assert "Redis connection failed" in caplog.text

def test_clear_cache_methods_are_importable():
    from backend.bcssm_backend.cache_utils import (
        clear_user_cache,
        clear_duty_cache,
        clear_feedback_cache,
        clear_all_cache
    )

    assert callable(clear_user_cache)
    assert callable(clear_duty_cache)
    assert callable(clear_feedback_cache)
    assert callable(clear_all_cache)

def test_cache_clearing_integration_with_data_changes(mock_readonly, mock_cache):
    mock_readonly.return_value = [('Alice Smith','SectionA','RoleA','TeamA')]

    result1 = user_queries.get_all_users()
    initial_db_calls = mock_readonly.call_count

    cache_utils.clear_user_cache()

    mock_cache.get.return_value = None
    mock_readonly.return_value = [('Bob Jones','SectionB','RoleB','TeamB')]
    result2 = user_queries.get_all_users()

    assert result1 == ['Alice Smith']
    assert result2 == ['Bob Jones']
    mock_cache.delete.assert_called()
    assert mock_readonly.call_count == initial_db_calls + 1

def test_clear_user_cache_logs_correctly(mock_cache, caplog):
    with caplog.at_level(logging.INFO):
        cache_utils.clear_user_cache()

    assert "Cleared user-related caches" in caplog.text

def test_clear_duty_cache_logs_correctly(mock_cache, caplog):
    with caplog.at_level(logging.INFO):
        cache_utils.clear_duty_cache()

    assert "Cleared duty-related caches" in caplog.text

def test_clear_feedback_cache_logs_correctly(mock_cache, caplog):
    with caplog.at_level(logging.INFO):
        cache_utils.clear_feedback_cache()

    assert "Cleared feedback caches" in caplog.text

def test_clear_all_cache_logs_correctly(mock_cache, caplog):
    with caplog.at_level(logging.INFO):
        cache_utils.clear_all_cache()

    assert "Cleared all caches" in caplog.text

# ─── Tests for cache management in realistic scenarios ──────────────────────

def test_cache_clear_after_user_update_scenario(mock_readonly, mock_cache):
    mock_readonly.return_value = [('Alice Smith','SectionA','RoleA','TeamA')]
    initial_users = user_queries.get_all_users()

    cache_utils.clear_user_cache()

    mock_cache.get.return_value = None
    mock_readonly.return_value = [('Alice Jones','SectionA','RoleA','TeamA')]

    updated_users = user_queries.get_all_users()

    assert initial_users == ['Alice Smith']
    assert updated_users == ['Alice Jones']
    mock_cache.delete.assert_called()

def test_cache_clear_after_duty_schedule_update_scenario(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        (1, 0, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}])
    ]
    initial_schedule = duty_queries.get_duty_schedule()

    with patch('backend.bcssm_backend.cache_utils.clear_group') as mock_cg:
        cache_utils.clear_duty_cache()
        mock_cg.assert_called_once_with("duties")

    mock_cache.get.return_value = None
    mock_readonly.return_value = [
        (1, 0, "Kitchen Duty", "Clean kitchen UPDATED", "Team A", [{"name": "Bob", "week": "Both"}])
    ]
    updated_schedule = duty_queries.get_duty_schedule()

    assert len(initial_schedule) == 14
    assert len(updated_schedule) == 14

# ─── Edge case tests ─────────────────────────────────────────────────────────

def test_clear_duty_cache_with_different_dates(mock_cache):
    for _ in range(3):
        with patch('backend.bcssm_backend.cache_utils.clear_group') as mock_cg:
            cache_utils.clear_duty_cache()
            mock_cg.assert_called_once_with("duties")

def test_multiple_cache_clears_in_sequence(mock_cache):
    cache_utils.clear_user_cache()
    cache_utils.clear_duty_cache()
    cache_utils.clear_feedback_cache()
    cache_utils.clear_all_cache()

    assert mock_cache.delete.call_count >= 1
    assert mock_cache.clear.call_count >= 1

# ─── Tests for get_all_sections_with_users() ─────────────────────────────────

def test_get_all_sections_with_users_happy_path(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('Minis', 1, 'Alice Smith', 'Section Leader', 'Both'),
        ('Minis', 1, 'Bob Jones', 'Team Member', 'Week A'),
        ('Micros', 2, 'Charlie Brown', 'Section Leader', 'Week B'),
        ('Unassigned', 999, 'Dave Wilson', 'Team Member', 'Both')
    ]

    result = section_queries.get_all_sections_with_users()

    assert isinstance(result, list)
    assert len(result) == 3

    minis_section = next(s for s in result if s['name'] == 'Minis')
    assert minis_section['display_order'] == 1
    assert minis_section['user_count'] == 2
    assert len(minis_section['users']) == 2
    assert minis_section['users'][0] == {'name': 'Alice Smith', 'role': 'Section Leader', 'week': 'Both'}
    assert minis_section['users'][1] == {'name': 'Bob Jones', 'role': 'Team Member', 'week': 'Week A'}

    micros_section = next(s for s in result if s['name'] == 'Micros')
    assert micros_section['user_count'] == 1
    assert micros_section['users'][0] == {'name': 'Charlie Brown', 'role': 'Section Leader', 'week': 'Week B'}

    unassigned_section = next(s for s in result if s['name'] == 'Unassigned')
    assert unassigned_section['display_order'] == 999
    assert unassigned_section['user_count'] == 1

    mock_cache.get.assert_called_once_with('sections:with_users:all_v6')
    mock_cache.set.assert_called_once_with('sections:with_users:all_v6', result, timeout=1800)

    sql = mock_readonly.call_args[0][0]
    assert "RIGHT JOIN users u ON s.id = u.section_id" in sql
    assert "COALESCE(s.name, 'Unassigned')" in sql
    assert "WHEN u.role = 'Admin' THEN 'Section Leader'" in sql
    assert "u.week" in sql
    assert "ORDER BY" in sql

def test_get_all_sections_with_users_cache_hit(mock_readonly, mock_cache):
    cached_data = [
        {
            "name": "Cached Section",
            "display_order": 1,
            "users": [{"name": "Cached User", "role": "Cached Role", "week": "Both"}],
            "user_count": 1
        }
    ]
    mock_cache.get.return_value = cached_data

    result = section_queries.get_all_sections_with_users()

    assert result == cached_data
    mock_cache.get.assert_called_once_with('sections:with_users:all_v6')
    mock_readonly.assert_not_called()
    mock_cache.set.assert_not_called()

def test_get_all_sections_with_users_empty_result(mock_readonly, mock_cache):
    mock_readonly.return_value = []

    result = section_queries.get_all_sections_with_users()

    assert result == []
    mock_cache.get.assert_called_once_with('sections:with_users:all_v6')
    mock_cache.set.assert_called_once_with('sections:with_users:all_v6', [], timeout=1800)

def test_get_all_sections_with_users_db_failure_returns_error(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("Database connection failed")

    result = section_queries.get_all_sections_with_users()

    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to fetch sections with users" in result["error"]
    assert "Database connection failed" in result["error"]

    mock_cache.set.assert_called_once_with('sections:with_users:all_v6', result, timeout=60)

def test_get_all_sections_with_users_admin_role_conversion(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('TestSection', 1, 'Admin User', 'Section Leader', 'Both'),
        ('TestSection', 1, 'Regular User', 'Team Member', 'Week A')
    ]

    result = section_queries.get_all_sections_with_users()

    section = result[0]
    admin_user = next(u for u in section['users'] if u['name'] == 'Admin User')
    assert admin_user['role'] == 'Section Leader'
    assert admin_user['week'] == 'Both'

def test_get_all_sections_with_users_sorting(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('Zebra Section', 3, 'User A', 'Team Member', 'Both'),
        ('Alpha Section', 1, 'User B', 'Team Member', 'Week A'),
        ('Beta Section', 1, 'User C', 'Team Member', 'Week B'),
        ('Unassigned', 999, 'User D', 'Team Member', 'Both')
    ]

    result = section_queries.get_all_sections_with_users()

    section_names = [s['name'] for s in result]
    assert section_names == ['Alpha Section', 'Beta Section', 'Zebra Section', 'Unassigned']

# ─── Tests for get_section_statistics() ──────────────────────────────────────

def test_get_section_statistics_happy_path(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('Minis', 1, 5, 1, 2, 2),
        ('Micros', 2, 3, 1, 1, 1),
        ('Unassigned', 999, 2, 0, 0, 2)
    ]

    result = section_queries.get_section_statistics()

    assert isinstance(result, list)
    assert len(result) == 3

    minis_stats = next(s for s in result if s['section_name'] == 'Minis')
    assert minis_stats['display_order'] == 1
    assert minis_stats['total_users'] == 5
    assert minis_stats['section_leaders'] == 1
    assert minis_stats['team_leaders'] == 2
    assert minis_stats['other_roles'] == 2

    micros_stats = next(s for s in result if s['section_name'] == 'Micros')
    assert micros_stats['total_users'] == 3
    assert micros_stats['section_leaders'] == 1

    unassigned_stats = next(s for s in result if s['section_name'] == 'Unassigned')
    assert unassigned_stats['display_order'] == 999
    assert unassigned_stats['section_leaders'] == 0

    mock_cache.get.assert_called_once_with('sections:statistics:summary')
    mock_cache.set.assert_called_once_with('sections:statistics:summary', result, timeout=3600)

    sql = mock_readonly.call_args[0][0]
    assert "RIGHT JOIN users u ON s.id = u.section_id" in sql
    assert "COUNT(u.id) AS total_users" in sql
    assert "COUNT(CASE WHEN u.role IN ('Section Leader', 'Admin')" in sql
    assert "COUNT(CASE WHEN u.role = 'Team Leader'" in sql
    assert "GROUP BY s.id, s.name, s.display_order" in sql

def test_get_section_statistics_cache_hit(mock_readonly, mock_cache):
    cached_stats = [
        {
            "section_name": "Cached Section",
            "display_order": 1,
            "total_users": 10,
            "section_leaders": 2,
            "team_leaders": 3,
            "other_roles": 5
        }
    ]
    mock_cache.get.return_value = cached_stats

    result = section_queries.get_section_statistics()

    assert result == cached_stats
    mock_cache.get.assert_called_once_with('sections:statistics:summary')
    mock_readonly.assert_not_called()
    mock_cache.set.assert_not_called()

def test_get_section_statistics_empty_result(mock_readonly, mock_cache):
    mock_readonly.return_value = []

    result = section_queries.get_section_statistics()

    assert result == []
    mock_cache.get.assert_called_once_with('sections:statistics:summary')
    mock_cache.set.assert_called_once_with('sections:statistics:summary', [], timeout=3600)

def test_get_section_statistics_db_failure_returns_error(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("Statistics query failed")

    result = section_queries.get_section_statistics()

    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to fetch section statistics" in result["error"]
    assert "Statistics query failed" in result["error"]

    mock_cache.set.assert_called_once_with('sections:statistics:summary', result, timeout=60)

def test_get_section_statistics_role_counting(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('TestSection', 1, 6, 2, 1, 3)
    ]

    result = section_queries.get_section_statistics()

    stats = result[0]
    assert stats['total_users'] == 6
    assert stats['section_leaders'] == 2
    assert stats['team_leaders'] == 1
    assert stats['other_roles'] == 3

    assert stats['section_leaders'] + stats['team_leaders'] + stats['other_roles'] == stats['total_users']

# ─── Tests for get_users_by_section() (consolidated) ─────────────────────────

def test_get_users_by_section_normal_section(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('Alice Smith', 'Section Leader'),
        ('Bob Jones', 'Team Member'),
        ('Charlie Brown', 'Team Leader')
    ]

    result = section_queries.get_users_by_section("Minis")

    assert isinstance(result, list)
    assert result == [
        {"name": "Alice Smith", "role": "Section Leader"},
        {"name": "Bob Jones", "role": "Team Member"},
        {"name": "Charlie Brown", "role": "Team Leader"}
    ]
    mock_cache.get.assert_called_once_with('users:section:Minis')
    mock_cache.set.assert_called_once_with('users:section:Minis', result, timeout=1800)
    sql, params = mock_readonly.call_args[0]
    assert "INNER JOIN sections s ON u.section_id = s.id" in sql
    assert "WHERE s.name = :section_name" in sql
    assert "WHEN u.role = 'Admin' THEN 'Section Leader'" in sql
    assert params == {"section_name": "Minis"}

def test_get_users_by_section_unassigned(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('Dave Wilson', 'Team Member'),
        ('Eve Davis', 'Section Leader'),
    ]

    result = section_queries.get_users_by_section("Unassigned")

    assert result == [
        {"name": "Dave Wilson", "role": "Team Member"},
        {"name": "Eve Davis", "role": "Section Leader"},
    ]
    mock_cache.get.assert_called_once_with('users:section:Unassigned')
    mock_cache.set.assert_called_once_with('users:section:Unassigned', result, timeout=1800)
    sql, params = mock_readonly.call_args[0]
    assert "WHERE u.section_id IS NULL" in sql
    assert "INNER JOIN sections" not in sql
    assert params == {}

def test_get_users_by_section_admin_role_mapped(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ('Admin User', 'Section Leader'),
        ('Regular User', 'Team Member'),
    ]

    result = section_queries.get_users_by_section("TestSection")

    admin_user = next(u for u in result if u['name'] == 'Admin User')
    assert admin_user['role'] == 'Section Leader'

def test_get_users_by_section_cache_hit(mock_readonly, mock_cache):
    cached_users = [{"name": "Cached User", "role": "Cached Role"}]
    mock_cache.get.return_value = cached_users

    result = section_queries.get_users_by_section("TestSection")

    assert result == cached_users
    mock_cache.get.assert_called_once_with('users:section:TestSection')
    mock_readonly.assert_not_called()
    mock_cache.set.assert_not_called()

def test_get_users_by_section_empty_result(mock_readonly, mock_cache):
    mock_readonly.return_value = []

    result = section_queries.get_users_by_section("EmptySection")

    assert result == []
    mock_cache.set.assert_called_once_with('users:section:EmptySection', [], timeout=1800)

def test_get_users_by_section_db_failure_returns_error(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("Section query failed")

    result = section_queries.get_users_by_section("TestSection")

    assert isinstance(result, dict)
    assert "Failed to fetch users by section" in result["error"]
    assert "Section query failed" in result["error"]
    mock_cache.set.assert_called_once_with('users:section:TestSection', result, timeout=60)

# ─── Tests for clear_user_cache() updates ────────────────────────────────────

def test_clear_user_cache_includes_new_keys(mock_cache):
    groups_cleared = []
    with patch(
        'backend.bcssm_backend.cache_utils.clear_group',
        side_effect=lambda g: groups_cleared.append(g),
    ):
        cache_utils.clear_user_cache()
    assert set(groups_cleared) == {"users", "sections"}


def test_clear_user_cache_handles_get_sections_error(mock_cache, caplog):
    with caplog.at_level(logging.INFO):
        cache_utils.clear_user_cache()
    assert "Cleared user-related caches" in caplog.text


def test_clear_user_cache_handles_empty_sections_list(mock_cache):
    cache_utils.clear_user_cache()
    deleted_keys = {c.args[0] for c in mock_cache.delete.call_args_list}
    assert "users:all:list" in deleted_keys
    assert "sections:all:list" in deleted_keys
    assert "sections:with_users:all_v6" in deleted_keys
    assert "sections:statistics:summary" in deleted_keys

# ─── Integration tests for the new methods ───────────────────────────────────

def test_section_methods_integration_workflow(mock_readonly, mock_cache):
    sections_with_users_data = [
        ('Minis', 1, 'Alice Smith', 'Section Leader', 'Both'),
        ('Minis', 1, 'Bob Jones', 'Team Member', 'Week A'),
        ('Micros', 2, 'Charlie Brown', 'Section Leader', 'Week B')
    ]

    statistics_data = [
        ('Minis', 1, 2, 1, 0, 1),
        ('Micros', 2, 1, 1, 0, 0)
    ]

    minis_users_data = [
        ('Alice Smith', 'Section Leader'),
        ('Bob Jones', 'Team Member')
    ]

    mock_readonly.return_value = sections_with_users_data
    sections_result = section_queries.get_all_sections_with_users()
    assert len(sections_result) == 2
    assert sections_result[0]['name'] == 'Minis'
    assert sections_result[0]['user_count'] == 2

    mock_readonly.return_value = statistics_data
    stats_result = section_queries.get_section_statistics()
    assert len(stats_result) == 2
    assert stats_result[0]['section_name'] == 'Minis'
    assert stats_result[0]['total_users'] == 2

    mock_readonly.return_value = minis_users_data
    users_result = section_queries.get_users_by_section("Minis")
    assert len(users_result) == 2
    assert users_result[0]['name'] == 'Alice Smith'

    assert mock_cache.get.call_count == 3
    assert mock_cache.set.call_count == 3

def test_error_handling_consistency_across_methods(mock_readonly, mock_cache):
    error_message = "Database connection lost"
    mock_readonly.side_effect = SQLAlchemyError(error_message)

    methods_to_test = [
        (section_queries.get_all_sections_with_users, "Failed to fetch sections with users"),
        (section_queries.get_section_statistics, "Failed to fetch section statistics"),
        (lambda: section_queries.get_users_by_section("TestSection"), "Failed to fetch users by section")
    ]

    for method, expected_error_prefix in methods_to_test:
        result = method()

        assert isinstance(result, dict)
        assert "error" in result
        assert expected_error_prefix in result["error"]
        assert error_message in result["error"]

# ─── Tests for _cycle_week_for_date() and get_current_cycle_week() ───────────

def test_cycle_week_for_date_week_a_start():
    duty_queries._cycle_week_for_date.cache_clear()
    assert duty_queries._cycle_week_for_date(duty_queries.CYCLE_ANCHOR.date()) == 0

def test_cycle_week_for_date_week_b_start():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    assert duty_queries._cycle_week_for_date((duty_queries.CYCLE_ANCHOR + timedelta(weeks=1)).date()) == 1

def test_cycle_week_for_date_full_camp_schedule():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    anchor = duty_queries.CYCLE_ANCHOR.date()
    for i in range(14):
        d = anchor + timedelta(days=i)
        expected = 0 if i < 7 else 1
        assert duty_queries._cycle_week_for_date(d) == expected, f"Day {i} ({d}) should be cycle {expected}"

def test_cycle_week_for_date_edge_cases():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    anchor = duty_queries.CYCLE_ANCHOR.date()
    test_cases = [
        (anchor + timedelta(days=-1), 1, "Day before anchor"),
        (anchor + timedelta(days=0),  0, "Anchor (Week A start)"),
        (anchor + timedelta(days=6),  0, "Last day of Week A"),
        (anchor + timedelta(days=7),  1, "First day of Week B"),
        (anchor + timedelta(days=13), 1, "Last day of Week B"),
        (anchor + timedelta(days=14), 0, "Week A again"),
        (anchor + timedelta(days=28), 0, "Week A after month boundary"),
        (anchor + timedelta(days=35), 1, "Week B after month boundary"),
    ]
    for d, expected, description in test_cases:
        result = duty_queries._cycle_week_for_date(d)
        assert result == expected, f"{description} ({d}): expected {expected}, got {result}"

def test_cycle_week_for_date_caching_same_date():
    duty_queries._cycle_week_for_date.cache_clear()
    d = duty_queries.CYCLE_ANCHOR.date()
    duty_queries._cycle_week_for_date(d)
    duty_queries._cycle_week_for_date(d)
    info = duty_queries._cycle_week_for_date.cache_info()
    assert info.hits == 1
    assert info.misses == 1

def test_cycle_week_for_date_different_dates_independent():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    week_a = duty_queries.CYCLE_ANCHOR.date()
    week_b = (duty_queries.CYCLE_ANCHOR + timedelta(weeks=1)).date()

    assert duty_queries._cycle_week_for_date(week_a) == 0
    assert duty_queries._cycle_week_for_date(week_b) == 1

    info = duty_queries._cycle_week_for_date.cache_info()
    assert info.currsize == 2
    assert info.misses == 2

    assert duty_queries._cycle_week_for_date(week_a) == 0
    assert duty_queries._cycle_week_for_date(week_b) == 1
    assert duty_queries._cycle_week_for_date.cache_info().hits == 2

def test_cycle_week_for_date_maxsize_eviction():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    anchor = duty_queries.CYCLE_ANCHOR.date()

    duty_queries._cycle_week_for_date(anchor)
    duty_queries._cycle_week_for_date(anchor + timedelta(weeks=1))
    assert duty_queries._cycle_week_for_date.cache_info().currsize == 2

    duty_queries._cycle_week_for_date(anchor + timedelta(weeks=2))
    assert duty_queries._cycle_week_for_date.cache_info().currsize == 2

def test_cycle_week_for_date_long_term_pattern():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    anchor = duty_queries.CYCLE_ANCHOR.date()
    for week_num in range(8):
        d = anchor + timedelta(weeks=week_num)
        expected = week_num % 2
        assert duty_queries._cycle_week_for_date(d) == expected, f"Week {week_num} ({d}): expected {expected}"

def test_cycle_week_for_date_matches_duty_schedule_calculation():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    anchor = duty_queries.CYCLE_ANCHOR.date()
    test_dates = [anchor + timedelta(weeks=n) for n in range(5)]
    for d in test_dates:
        days = (d - anchor).days
        expected = (days // 7) % 2
        assert duty_queries._cycle_week_for_date(d) == expected, f"Mismatch for {d}"

def test_cycle_week_for_date_before_anchor():
    from datetime import timedelta
    duty_queries._cycle_week_for_date.cache_clear()
    anchor = duty_queries.CYCLE_ANCHOR.date()
    test_cases = [
        anchor + timedelta(days=-1),
        anchor + timedelta(days=-7),
        anchor + timedelta(days=-14),
    ]
    for d in test_cases:
        days = (d - anchor).days
        expected = (days // 7) % 2
        assert duty_queries._cycle_week_for_date(d) == expected, f"Before-anchor mismatch for {d}"

def test_cycle_week_for_date_cache_info():
    duty_queries._cycle_week_for_date.cache_clear()
    info = duty_queries._cycle_week_for_date.cache_info()
    assert info.currsize == 0
    assert info.maxsize == 2

    duty_queries._cycle_week_for_date(duty_queries.CYCLE_ANCHOR.date())
    info = duty_queries._cycle_week_for_date.cache_info()
    assert info.currsize == 1
    assert info.misses == 1
    assert info.hits == 0

def test_get_current_cycle_week_delegates_to_date_helper(monkeypatch):
    captured = []

    def fake_cycle_week(d):
        captured.append(d)
        return 99

    monkeypatch.setattr(duty_queries, '_cycle_week_for_date', fake_cycle_week)
    result = duty_queries.get_current_cycle_week()

    assert result == 99
    assert len(captured) == 1
    assert captured[0] == datetime.now().date()

def test_get_current_cycle_week_integration_with_get_user_duty(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 0  # Monday
    monkeypatch.setattr(duty_queries, 'datetime', FakeDatetime)
    monkeypatch.setattr(duty_queries, 'get_current_cycle_week', lambda: 1)

    mock_readonly.return_value = [
        ("Test User", "Test Section", "Leader", "Test Team", "Test Duty")
    ]

    result = duty_queries.get_user_duty("Test User")

    _sql, params = mock_readonly.call_args[0]
    assert params['cycle_week'] == 1
    assert params['day'] == 1  # Monday: (0 + 1) % 7 = 1

    assert result['user'] == "Test User"
    assert result['duty'] == "Test Duty"


# ─── Tests for get_feedback_by_date ─────────────────────────────────────────

def test_get_feedback_by_date_success(monkeypatch):
    mock_exec = MagicMock(return_value=[("Minis", "Great job"), ("Majors", None)])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    result = feedback_queries.get_feedback_by_date("2025-06-07")
    assert result == {"Minis": "Great job", "Majors": "No feedback available"}


def test_get_feedback_by_date_exception(monkeypatch):
    mock_exec = MagicMock(side_effect=SQLAlchemyError("DB fail"))
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    with pytest.raises(SQLAlchemyError):
        feedback_queries.get_feedback_by_date("2025-06-07")


# ─── Tests for get_user_info ─────────────────────────────────────────────────

def test_get_user_info_found(monkeypatch):
    mock_exec = MagicMock(return_value=[("Alice", "Leader", "Minis")])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    info = user_queries.get_user_info("Alice")
    assert info == {"name": "Alice", "role": "Leader", "section": "Minis"}


def test_get_user_info_not_found(monkeypatch):
    mock_exec = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    assert user_queries.get_user_info("Bob") is None


def test_get_user_info_exception(monkeypatch):
    mock_exec = MagicMock(side_effect=SQLAlchemyError("Oops"))
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    with pytest.raises(SQLAlchemyError):
        user_queries.get_user_info("Alice")


def test_get_user_info_by_id_found(monkeypatch):
    mock_exec = MagicMock(return_value=[("Alice", "Leader", "Minis")])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    info = user_queries.get_user_info_by_id(42)
    assert info == {"name": "Alice", "role": "Leader", "section": "Minis"}


def test_get_user_id_by_name_found(monkeypatch):
    mock_exec = MagicMock(return_value=[(7,)])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    assert user_queries.get_user_id_by_name("Alice") == 7


def test_get_user_id_by_name_not_found(monkeypatch):
    mock_exec = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    assert user_queries.get_user_id_by_name("Ghost") is None


def test_get_user_id_by_name_db_error(monkeypatch):
    from backend.bcssm_backend.exceptions import DatabaseError
    mock_exec = MagicMock(side_effect=DatabaseError("DB error"))
    monkeypatch.setattr("backend.bcssm_backend.db.execute_readonly_query", mock_exec)
    assert user_queries.get_user_id_by_name("Alice") is None


# ─── Tests for save_devos_feedback ───────────────────────────────────────────

def test_save_devos_feedback_success(monkeypatch):
    mock_exec = MagicMock(return_value=[(5,)])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_query", mock_exec)
    feedback_queries.save_devos_feedback("Minis", "2025-06-07", "Great session", 1)
    mock_exec.assert_called_once()
    call_params = mock_exec.call_args[0][1]
    assert call_params['section_name'] == 'Minis'
    assert call_params['new_feedback'] == 'Great session'
    assert call_params['date_str'] == '2025-06-07'
    assert call_params['editor_id'] == 1


def test_save_devos_feedback_section_not_found(monkeypatch):
    mock_exec = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_query", mock_exec)
    with pytest.raises(ValidationError, match="Section not found"):
        feedback_queries.save_devos_feedback("Unknown", "2025-06-07", "feedback", 1)


def test_save_devos_feedback_db_error(monkeypatch):
    mock_exec = MagicMock(side_effect=SQLAlchemyError("DB error"))
    monkeypatch.setattr("backend.bcssm_backend.db.execute_query", mock_exec)
    with pytest.raises(SQLAlchemyError):
        feedback_queries.save_devos_feedback("Minis", "2025-06-07", "feedback", 1)


def test_save_devos_feedback_uses_single_query(monkeypatch):
    mock_exec = MagicMock(return_value=[(7,)])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_query", mock_exec)
    feedback_queries.save_devos_feedback("Seniors", "2025-06-07", "Good work", 2)
    assert mock_exec.call_count == 1
    query_text = mock_exec.call_args[0][0]
    assert "INSERT INTO feedback" in query_text
    assert "FROM sections" in query_text
    assert "RETURNING" in query_text


def test_save_devos_feedback_clears_feedback_cache_on_success(monkeypatch):
    mock_exec = MagicMock(return_value=[(5,)])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_query", mock_exec)
    mock_clear = MagicMock()
    monkeypatch.setattr("backend.bcssm_backend.feedback_queries.clear_group", mock_clear)
    feedback_queries.save_devos_feedback("Minis", "2025-06-07", "Great session", 1)
    mock_clear.assert_called_once_with("feedback")


def test_save_devos_feedback_does_not_clear_cache_when_section_not_found(monkeypatch):
    mock_exec = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.db.execute_query", mock_exec)
    mock_clear = MagicMock()
    monkeypatch.setattr("backend.bcssm_backend.feedback_queries.clear_group", mock_clear)
    with pytest.raises(ValidationError):
        feedback_queries.save_devos_feedback("Unknown", "2025-06-07", "feedback", 1)
    mock_clear.assert_not_called()


# ─── authenticate_user ────────────────────────────────────────────────────────
_FAKE_HASH = "$2b$12$fakehashfakehashfakehashfakehashfakehashfakehashfakeha"


def test_authenticate_user_success(mock_readonly, mocker):
    mock_readonly.return_value = [(1, "Alice", "Section Leader", "Minis", _FAKE_HASH)]
    mocker.patch("backend.bcssm_backend.auth_queries.bcrypt.checkpw", return_value=True)
    result = auth_queries.authenticate_user("Alice", "secret123")
    assert result == {
        "id": 1,
        "name": "Alice",
        "role": "Section Leader",
        "section_name": "Minis",
        "can_edit_all": True,
    }


def test_authenticate_user_not_found_raises(mock_readonly):
    mock_readonly.return_value = []
    with pytest.raises(AuthenticationError):
        auth_queries.authenticate_user("Ghost", "secret123")


def test_authenticate_user_no_password_hash_raises(mock_readonly):
    mock_readonly.return_value = [(1, "Alice", "Section Leader", "Minis", None)]
    with pytest.raises(AuthenticationError):
        auth_queries.authenticate_user("Alice", "secret123")


def test_authenticate_user_wrong_password_raises(mock_readonly, mocker):
    mock_readonly.return_value = [(1, "Alice", "Section Leader", "Minis", _FAKE_HASH)]
    mocker.patch("backend.bcssm_backend.auth_queries.bcrypt.checkpw", return_value=False)
    with pytest.raises(AuthenticationError):
        auth_queries.authenticate_user("Alice", "wrongpassword")


def test_authenticate_user_null_section_coalesced(mock_readonly, mocker):
    mock_readonly.return_value = [(1, "Alice", "Team Member", "Unassigned", _FAKE_HASH)]
    mocker.patch("backend.bcssm_backend.auth_queries.bcrypt.checkpw", return_value=True)
    result = auth_queries.authenticate_user("Alice", "secret123")
    assert result["section_name"] == "Unassigned"


def test_authenticate_user_uses_silent_query(mock_readonly, mocker, caplog):
    mock_readonly.return_value = [(1, "Alice", "Section Leader", "Minis", _FAKE_HASH)]
    mocker.patch("backend.bcssm_backend.auth_queries.bcrypt.checkpw", return_value=True)
    with caplog.at_level(logging.INFO, logger="backend.bcssm_backend.auth_queries"):
        auth_queries.authenticate_user("Alice", "secret123")
    assert mock_readonly.call_args.kwargs.get("silent") is True
    info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert not any("Alice" in m for m in info_messages)
    assert not any("user_name" in m for m in info_messages)


def test_authenticate_user_malformed_hash_raises(mock_readonly, mocker):
    mock_readonly.return_value = [(1, "Alice", "Section Leader", "Minis", _FAKE_HASH)]
    mocker.patch("backend.bcssm_backend.auth_queries.bcrypt.checkpw", side_effect=ValueError("invalid hash"))
    with pytest.raises(AuthenticationError):
        auth_queries.authenticate_user("Alice", "secret123")


def test_authenticate_user_db_error_propagates(mock_readonly):
    mock_readonly.side_effect = SQLAlchemyError("db down")
    with pytest.raises(SQLAlchemyError):
        auth_queries.authenticate_user("Alice", "secret123")


@pytest.mark.parametrize("role,expected", [
    ("Section Leader", True),
    ("Team Leader", True),
    ("Admin", True),
    ("Team Member", False),
])
def test_authenticate_user_can_edit_all_roles(mock_readonly, mocker, role, expected):
    mock_readonly.return_value = [(1, "Alice", role, "Minis", _FAKE_HASH)]
    mocker.patch("backend.bcssm_backend.auth_queries.bcrypt.checkpw", return_value=True)
    result = auth_queries.authenticate_user("Alice", "secret123")
    assert result["can_edit_all"] is expected


# ─── cache_user_login ─────────────────────────────────────────────────────────
def test_cache_user_login_writes_correct_key_and_ttl(mock_cache):
    user_data = {"id": 1, "name": "Alice", "role": "Section Leader",
                 "section_name": "Minis", "can_edit_all": True}
    auth_queries.cache_user_login(user_data)
    mock_cache.set.assert_called_once_with("user:data:Alice", user_data, timeout=1800)


def test_cache_user_login_swallows_redis_error(mock_cache):
    mock_cache.set.side_effect = RedisError("Redis down")
    auth_queries.cache_user_login({"name": "Alice"})  # must not raise


# ─── evict_user_login_cache ───────────────────────────────────────────────────
def test_evict_user_login_cache_deletes_correct_key(mock_cache):
    auth_queries.evict_user_login_cache("Alice")
    mock_cache.delete.assert_called_once_with("user:data:Alice")


def test_evict_user_login_cache_swallows_redis_error(mock_cache):
    mock_cache.delete.side_effect = RedisError("Redis down")
    auth_queries.evict_user_login_cache("Alice")  # must not raise


# ─── get_user_role ────────────────────────────────────────────────────────────
def test_get_user_role_found(mock_readonly):
    mock_readonly.return_value = [("Admin",)]
    result = auth_queries.get_user_role("Harrison")
    assert result == "Admin"
    assert mock_readonly.call_args.kwargs.get("silent") is True


def test_get_user_role_not_found(mock_readonly):
    mock_readonly.return_value = []
    result = auth_queries.get_user_role("Ghost")
    assert result is None


# ─── get_all_users_password_status ───────────────────────────────────────────
def test_get_all_users_password_status(mock_readonly):
    mock_readonly.return_value = [("Alice", True), ("Bob", False)]
    result = auth_queries.get_all_users_password_status()
    assert result == [
        {"name": "Alice", "has_password": True},
        {"name": "Bob", "has_password": False},
    ]


# ─── set_user_password ────────────────────────────────────────────────────────
def test_set_user_password_found(mock_db_session):
    mock_result = MagicMock()
    mock_result.returns_rows = True
    mock_result.fetchall.return_value = [(1,)]
    mock_db_session.execute.return_value = mock_result
    assert auth_queries.set_user_password("Alice", "$2b$12$hash") is True


def test_set_user_password_not_found(mock_db_session):
    mock_result = MagicMock()
    mock_result.returns_rows = True
    mock_result.fetchall.return_value = []
    mock_db_session.execute.return_value = mock_result
    assert auth_queries.set_user_password("Ghost", "$2b$12$hash") is False


def test_set_user_password_redacts_hash_in_error_log(caplog):
    from backend.bcssm_backend.exceptions import DatabaseError
    with patch('backend.bcssm_backend.db.db') as mock_db:
        mock_db.session.begin.return_value.__enter__ = MagicMock(return_value=mock_db.session)
        mock_db.session.begin.return_value.__exit__ = MagicMock(return_value=None)
        mock_db.session.execute.side_effect = SQLAlchemyError("db down")
        with caplog.at_level(logging.ERROR, logger="backend.bcssm_backend.db"):
            with pytest.raises(Exception):
                _real_execute_query(
                    "UPDATE users SET password_hash = :hash WHERE name = :name RETURNING id",
                    {'hash': '$2b$12$realhash', 'name': 'Alice'},
                    silent=True,
                )
    error_messages = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert "$2b$12$realhash" not in error_messages
    assert "<redacted>" in error_messages
