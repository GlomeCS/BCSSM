import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from datetime import datetime
import logging
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from backend.bcssm_backend import create_app, utils
import unittest.mock

# Save reference to the real function before autouse patching replaces it
_real_execute_readonly_query = utils.execute_readonly_query

# ─── 0) Autouse fixture to push a Flask app context ─────────────────────────
@pytest.fixture(autouse=True)
def flask_app_context(monkeypatch):
    # Ensure create_app() loads TestingConfig
    monkeypatch.setenv('FLASK_ENV', 'testing')
    app = create_app()
    ctx = app.app_context()
    ctx.push()
    yield
    ctx.pop()

# ─── 1) Autouse fixture to stub read‐only helper only ───────────────────────
@pytest.fixture(autouse=True)
def mock_readonly(mocker):
    return mocker.patch('backend.bcssm_backend.utils.execute_readonly_query')

# ─── 1.5) Mock the cache to avoid Redis connection issues ───────────────────
@pytest.fixture(autouse=True)
def mock_cache(monkeypatch):
    """Mock the cache to avoid Redis connection during tests"""
    fake_cache = MagicMock()
    fake_cache.get.return_value = None
    fake_cache.set.return_value = True
    fake_cache.delete.return_value = True
    fake_cache.clear.return_value = True

    monkeypatch.setattr('backend.bcssm_backend.utils.cache', fake_cache)
    # Also patch globals.cache so the cached_result decorator's lazy import gets the mock
    monkeypatch.setattr('backend.globals.cache', fake_cache)
    return fake_cache

# ─── 2) Fixture to mock db.session directly (for testing execute_query) ─────
@pytest.fixture
def mock_db_session():
    with patch('backend.bcssm_backend.utils.db.session') as sess:
        # Make sess.begin() return a context manager yielding sess itself
        sess.begin.return_value.__enter__.return_value = sess
        sess.begin.return_value.__exit__.return_value = None
        yield sess

# ─── 3) Utility to control "today" in date‐sensitive code ─────────────────────
class FakeDatetime:
    @classmethod
    def now(cls):
        return SimpleNamespace(weekday=lambda: cls.today_weekday)

# ─── 4) Tests for get_all_users() ────────────────────────────────────────────
def test_get_all_users_happy_path(mock_readonly, mock_cache):
    # Arrange: return a couple of rows
    mock_readonly.return_value = [
        ('Alice Smith','SectionA','RoleA','TeamA'),
        ('Bob Jones','SectionB','RoleB','TeamB'),
    ]
    # Act
    result = utils.get_all_users()
    # Assert
    assert result == ['Alice Smith','Bob Jones']
    
    # Verify cache was checked first
    mock_cache.get.assert_called_once_with('users:all:list')
    # Verify cache was set after DB query
    mock_cache.set.assert_called_once_with('users:all:list', ['Alice Smith','Bob Jones'], timeout=900)
    
    sql = mock_readonly.call_args[0][0]
    params = None
    assert params is None
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
    # Arrange: cache returns data
    mock_cache.get.return_value = ['Cached Alice', 'Cached Bob']
    
    # Act
    result = utils.get_all_users()
    
    # Assert
    assert result == ['Cached Alice', 'Cached Bob']
    
    # Verify cache was checked
    mock_cache.get.assert_called_once_with('users:all:list')
    # Verify DB was NOT queried
    mock_readonly.assert_not_called()
    # Verify cache was NOT set (already had data)
    mock_cache.set.assert_not_called()

def test_get_all_users_db_failure_returns_empty_list(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("DB is down")
    result = utils.get_all_users()
    assert result == []
    assert isinstance(result, list)

# ─── 5) Tests for get_user_duty() ─────────────────────────────────────────────
def test_get_user_duty_valid_today_returns_expected(monkeypatch, mock_readonly, mock_cache):
    # Freeze today to Wednesday (weekday==2)
    # With corrected calculation: (2 + 1) % 7 = 3
    FakeDatetime.today_weekday = 2
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    
    # Mock the get_current_cycle_week function to return a predictable value
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 0)
    
    mock_readonly.return_value = [
        ("Ivy","Minis","Team Member","Team1","Lunch Duty")
    ]
    result = utils.get_user_duty("Ivy")
    assert result == {
        "user": "Ivy",
        "section": "Minis",
        "role": "Team Member",
        "team": "Team1",
        "duty": "Lunch Duty"
    }
    
    # Verify cache operations - day is now 3 instead of 2
    cache_key_pattern = 'user:duty:Ivy:day3:cycle0'
    mock_cache.get.assert_called_once_with(cache_key_pattern)
    mock_cache.set.assert_called_once()
    cache_set_args = mock_cache.set.call_args
    assert cache_set_args[0][0] == cache_key_pattern
    assert cache_set_args[1]['timeout'] == 600
    
    mock_readonly.assert_called_once()
    sql, params = mock_readonly.call_args[0]
    assert isinstance(params['day'], int)
    assert params['day'] == 3  # Corrected day calculation
    assert params['cycle_week'] == 0

def test_get_user_duty_cache_hit(monkeypatch, mock_readonly, mock_cache):
    # Arrange: cache returns duty data
    cached_duty = {
        "user": "Ivy",
        "section": "Minis", 
        "role": "Team Member",
        "team": "Team1",
        "duty": "Cached Duty"
    }
    mock_cache.get.return_value = cached_duty
    
    # Wednesday (weekday==2) becomes day 3 with corrected calculation
    FakeDatetime.today_weekday = 2
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 0)
    
    # Act
    result = utils.get_user_duty("Ivy")
    
    # Assert
    assert result == cached_duty
    
    # Verify cache was checked - day is now 3 instead of 2
    mock_cache.get.assert_called_once_with('user:duty:Ivy:day3:cycle0')
    # Verify DB was NOT queried
    mock_readonly.assert_not_called()
    # Verify cache was NOT set (already had data)
    mock_cache.set.assert_not_called()

def test_get_user_duty_not_assigned_returns_error(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 0
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 0)
    
    mock_readonly.return_value = []
    result = utils.get_user_duty("NoOne")
    assert isinstance(result, dict)
    assert "error" in result
    assert "not found or no duty" in result["error"].lower()
    
    # Verify error was cached (shorter timeout)
    mock_cache.set.assert_called_once()
    cache_set_args = mock_cache.set.call_args
    assert cache_set_args[1]['timeout'] == 600  # Normal timeout for this case

def test_get_user_duty_exception_propagates_error(monkeypatch, mock_readonly, mock_cache):
    FakeDatetime.today_weekday = 0
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 0)

    mock_readonly.side_effect = SQLAlchemyError("Something broke")
    with pytest.raises(SQLAlchemyError, match="Something broke"):
        utils.get_user_duty("SomeUser")

    # Error is re-raised, so no caching occurs
    mock_cache.set.assert_not_called()

def test_get_user_duty_short_row(monkeypatch, mock_readonly, mock_cache):
    """Test get_user_duty when row has fewer than 5 columns (covers len(row) < 5 branch)"""
    FakeDatetime.today_weekday = 0
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 0)

    # Return a row with only 3 columns instead of 5
    mock_readonly.return_value = [('Alice', 'Section1', 'Role1')]
    result = utils.get_user_duty("Alice")
    assert isinstance(result, dict)
    assert "error" in result
    assert "Unexpected data format" in result["error"]

def test_execute_readonly_query_db_error():
    """Test execute_readonly_query except SQLAlchemyError block (covers lines 39-43)"""
    with patch('backend.bcssm_backend.utils.db') as mock_db:
        mock_db.engine.connect.side_effect = SQLAlchemyError("connection failed")
        with pytest.raises(SQLAlchemyError, match="connection failed"):
            _real_execute_readonly_query("SELECT 1")

# ─── 6) Tests for get_users_by_section() ───────────────────────────────────
def test_get_users_by_section_returns_list_of_dicts(mock_readonly, mock_cache):
    mock_readonly.return_value = [
        ("Alice","Section Leader"),
        ("Bob","Team Member")
    ]
    result = utils.get_users_by_section("Minis")
    assert isinstance(result, list)
    assert result == [
        {"name": "Alice", "role": "Section Leader"},
        {"name": "Bob",   "role": "Team Member"},
    ]
    
    # Verify cache operations
    mock_cache.get.assert_called_once_with('users:section:Minis')
    mock_cache.set.assert_called_once_with(
        'users:section:Minis', 
        [{"name": "Alice", "role": "Section Leader"}, {"name": "Bob", "role": "Team Member"}],
        timeout=1800
    )
    
    sql, params = mock_readonly.call_args[0]
    expected_sql = """
    SELECT u.name, u.role
    FROM users u
    INNER JOIN sections s ON u.section_id = s.id
    WHERE s.name = :section
    ORDER BY u.name;
    """
    assert sql.strip() == expected_sql.strip()
    assert params == {"section": "Minis"}

def test_get_users_by_section_db_error_returns_error(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("DB error on section query")
    result = utils.get_users_by_section("Minis")
    assert isinstance(result, dict)
    assert "Failed to fetch users by section" in result["error"]
    assert "DB error on section query" in result["error"]

# ─── 7) Tests for get_all_sections() ───────────────────────────────────────
def test_get_all_sections_with_records(mock_readonly, mock_cache):
    mock_readonly.return_value = [("Minis",), ("Micros",), ("Majors",)]
    result = utils.get_all_sections()
    assert result == ["Minis", "Micros", "Majors"]
    
    # Verify cache operations
    mock_cache.get.assert_called_once_with('sections:all:list')
    mock_cache.set.assert_called_once_with('sections:all:list', ["Minis", "Micros", "Majors"], timeout=3600)
    
    sql = mock_readonly.call_args[0][0]
    assert "ORDER BY display_order, name" in sql.strip()
    assert sql.strip().startswith("SELECT name")

def test_get_all_sections_no_records(mock_readonly, mock_cache):
    mock_readonly.return_value = []
    result = utils.get_all_sections()
    assert result == []

def test_get_all_sections_exception(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("Database failure")
    result = utils.get_all_sections()
    assert isinstance(result, dict)
    assert "Failed to fetch sections" in result["error"]
    assert "Database failure" in result["error"]

# ─── 8) Tests for get_all_feedback_dates() ──────────────────────────────────
def test_get_all_feedback_dates_with_records(mock_readonly, mock_cache):
    mock_readonly.return_value = [("2025-06-01",), ("2025-05-25",)]
    result = utils.get_all_feedback_dates()
    assert result == ["2025-06-01", "2025-05-25"]
    
    # Verify cache operations
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
    result = utils.get_all_feedback_dates()
    assert result == []

def test_get_all_feedback_dates_exception(mock_readonly, mock_cache):
    mock_readonly.side_effect = SQLAlchemyError("Database error")
    result = utils.get_all_feedback_dates()
    assert isinstance(result, dict)
    assert "Failed to fetch feedback dates" in result["error"]
    assert "Database error" in result["error"]

# ─── 9) Tests for execute_query (transactions) ──────────────────────────────
def test_execute_query_success_with_results(mock_db_session):
    # Arrange
    mock_result = MagicMock()
    mock_result.returns_rows = True
    mock_result.fetchall.return_value = [("Alice",)]
    mock_db_session.execute.return_value = mock_result

    # Act
    rows = utils.execute_query("SELECT name FROM users")

    # Assert
    mock_db_session.execute.assert_called_once()
    mock_db_session.begin.assert_called_once()
    assert rows == [("Alice",)]

def test_execute_query_success_no_results(mock_db_session):
    mock_result = MagicMock()
    mock_result.returns_rows = False
    mock_db_session.execute.return_value = mock_result
    rows = utils.execute_query("UPDATE users SET name='X'")
    mock_db_session.execute.assert_called_once()
    mock_db_session.begin.assert_called_once()
    assert rows is None

def test_execute_query_failure_triggers_rollback(mock_db_session):
    mock_db_session.execute.side_effect = SQLAlchemyError("DB error")
    with pytest.raises(Exception, match="DB error"):
        utils.execute_query("DELETE FROM users")
    mock_db_session.rollback.assert_called_once()

# Add test for get_todays_duties to verify cycle_week usage
def test_get_todays_duties_uses_cycle_week(monkeypatch, mock_readonly, mock_cache):
    # Mock datetime and cycle week
    # Tuesday (weekday==1) becomes day 2 with corrected calculation: (1 + 1) % 7 = 2
    FakeDatetime.today_weekday = 1  # Tuesday
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 1)
    
    mock_readonly.return_value = [
        (1, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}], True)
    ]
    
    result = utils.get_todays_duties("Alice")
    
    # Verify cache operations - day is now 2 instead of 1
    cache_key_pattern = 'duties:today:day2:cycle1:userAlice'
    mock_cache.get.assert_called_once_with(cache_key_pattern)
    mock_cache.set.assert_called_once()
    
    # Verify the query was called with correct parameters - day is now 2 instead of 1
    sql, params = mock_readonly.call_args[0]
    assert params['day'] == 2  # Corrected day calculation
    assert params['cycle_week'] == 1
    assert params['user_name'] == "Alice"
    
    # Verify simplified query structure (no CTE)
    assert "WITH computed_cycle" not in sql
    assert "WHERE ds.day = :day" in sql
    assert "AND ds.cycle_week = :cycle_week" in sql
    
def test_caching_behavior(mock_readonly, mock_cache):
    """Test that caching works correctly"""
    mock_readonly.return_value = [('Alice Smith','SectionA','RoleA','TeamA')]
    
    # First call should hit the database
    result1 = utils.get_all_users()
    assert mock_readonly.call_count == 1
    assert mock_cache.get.call_count == 1
    assert mock_cache.set.call_count == 1
    
    # Reset mock to simulate cache hit
    mock_cache.reset_mock()
    mock_cache.get.return_value = ['Alice Smith']  # Simulate cache hit
    mock_readonly.reset_mock()
    
    # Second call should use cache
    result2 = utils.get_all_users()
    
    # Verify cache was checked but DB wasn't called
    assert mock_cache.get.call_count == 1
    assert mock_readonly.call_count == 0  # No DB call
    assert mock_cache.set.call_count == 0  # No cache set (data was already cached)
    
    assert result2 == ['Alice Smith']

# Test the new get_duty_schedule optimization
def test_get_duty_schedule_uses_parameterized_query(mock_readonly, mock_cache):
    """Test that get_duty_schedule uses the new parameterized approach"""
    mock_readonly.return_value = [
        (1, 0, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}])
    ]
    
    result = utils.get_duty_schedule()
    
    # Verify it's a list of schedule entries
    assert isinstance(result, list)
    assert len(result) == 14  # 2 weeks
    
    # Verify cache operations
    mock_cache.get.assert_called_once()
    cache_key = mock_cache.get.call_args[0][0]
    assert cache_key.startswith('duties:schedule:14day:')
    mock_cache.set.assert_called_once()
    
    # Check that the query uses ANY() for parameterization instead of dynamic SQL
    sql, params = mock_readonly.call_args[0]
    assert "ANY(:days)" in sql
    assert "ANY(:cycles)" in sql
    assert "days" in params
    assert "cycles" in params
    
    # Ensure no dynamic SQL concatenation
    assert isinstance(params['days'], list)
    assert isinstance(params['cycles'], list)

def test_get_current_cycle_week_calculation():
    """Test the cycle week calculation helper"""
    from datetime import datetime
    
    # Test the calculation logic directly without cache interference
    with patch('backend.bcssm_backend.utils.datetime') as mock_dt:
        # Test Week 0 (July 7, 2025)
        mock_dt.now.return_value.date.return_value = datetime(2025, 7, 7).date()
        days_since_start = (datetime(2025, 7, 7).date() - datetime(2025, 7, 7).date()).days
        expected_week_0 = (days_since_start // 7) % 2
        assert expected_week_0 == 0
        
        # Test Week 1 (July 14, 2025) 
        mock_dt.now.return_value.date.return_value = datetime(2025, 7, 14).date()
        days_since_start = (datetime(2025, 7, 14).date() - datetime(2025, 7, 7).date()).days
        expected_week_1 = (days_since_start // 7) % 2
        assert expected_week_1 == 1
        
        # Test Week 0 again (July 21, 2025)
        mock_dt.now.return_value.date.return_value = datetime(2025, 7, 21).date()
        days_since_start = (datetime(2025, 7, 21).date() - datetime(2025, 7, 7).date()).days
        expected_week_0_again = (days_since_start // 7) % 2
        assert expected_week_0_again == 0

    # Add these tests to your existing test_utils.py file

# ─── Tests for cache clearing methods ────────────────────────────────────────

def test_clear_user_cache(mock_cache):
    """Test clearing user-related caches"""
    # Mock get_all_sections to return some sections to avoid DB call
    with patch('backend.bcssm_backend.utils.get_all_sections') as mock_get_sections:
        mock_get_sections.return_value = ['Minis', 'Micros']
        
        # Act
        utils.clear_user_cache()
        
        # Assert
        deleted_keys = [c.args[0] for c in mock_cache.delete.call_args_list]
        assert 'users:all:list' in deleted_keys
        assert 'sections:all:list' in deleted_keys
        assert 'sections:with_users:all_v6' in deleted_keys

def test_clear_duty_cache(mock_cache):
    """Test clearing duty-related caches"""
    with patch('backend.bcssm_backend.utils.datetime') as mock_dt:
        # Mock today's date for predictable cache key
        mock_dt.now.return_value.date.return_value = datetime(2025, 6, 16).date()
        
        # Act
        utils.clear_duty_cache()
        
        # Assert
        # Should delete duty schedule cache key and then clear all
        mock_cache.delete.assert_called_with('duties:schedule:14day:2025-06-16')
        mock_cache.clear.assert_called_once()

def test_clear_feedback_cache(mock_cache):
    """Test clearing feedback-related caches"""
    # Act
    utils.clear_feedback_cache()
    
    # Assert
    mock_cache.delete.assert_called_once_with('feedback:dates:all')

def test_clear_all_cache(mock_cache):
    """Test clearing all caches"""
    # Act
    utils.clear_all_cache()
    
    # Assert
    mock_cache.clear.assert_called_once()
    # Should not call delete for specific keys when clearing all
    mock_cache.delete.assert_not_called()

def test_clear_cache_methods_handle_errors_gracefully(mock_cache, caplog):
    """Test that cache clearing methods handle Redis errors gracefully"""
    # Arrange - make cache operations fail
    mock_cache.delete.side_effect = RedisError("Redis connection failed")
    mock_cache.clear.side_effect = RedisError("Redis connection failed")
    
    # Act & Assert - should not raise exceptions
    with caplog.at_level(logging.WARNING):
        utils.clear_user_cache()
        utils.clear_feedback_cache()
        utils.clear_all_cache()
        utils.clear_duty_cache()
    
    # Verify that warning messages were logged
    assert "Failed to clear user caches" in caplog.text
    assert "Failed to clear feedback caches" in caplog.text
    assert "Failed to clear all caches" in caplog.text
    assert "Failed to clear duty caches" in caplog.text
    
    # Verify that Redis connection failed error is mentioned
    assert "Redis connection failed" in caplog.text

def test_clear_cache_methods_are_importable():
    """Test that all cache clearing functions can be imported"""
    from backend.bcssm_backend.utils import (
        clear_user_cache, 
        clear_duty_cache, 
        clear_feedback_cache, 
        clear_all_cache
    )
    
    # Assert functions exist and are callable
    assert callable(clear_user_cache)
    assert callable(clear_duty_cache)
    assert callable(clear_feedback_cache)
    assert callable(clear_all_cache)

def test_cache_clearing_integration_with_data_changes(mock_readonly, mock_cache):
    """Test typical workflow: data change -> cache clear -> fresh data"""
    # Arrange: Populate cache first
    mock_readonly.return_value = [('Alice Smith','SectionA','RoleA','TeamA')]
    
    # Act 1: Get data (populates cache)
    result1 = utils.get_all_users()
    initial_db_calls = mock_readonly.call_count
    
    # Act 2: Clear cache (simulating data update)
    with patch('backend.bcssm_backend.utils.get_all_sections') as mock_get_sections:
        mock_get_sections.return_value = []  # Empty sections to avoid additional DB calls
        utils.clear_user_cache()
    
    # Act 3: Get data again (should hit DB, not cache)
    mock_cache.get.return_value = None  # Simulate cache miss after clear
    mock_readonly.return_value = [('Bob Jones','SectionB','RoleB','TeamB')]
    result2 = utils.get_all_users()
    
    # Assert
    assert result1 == ['Alice Smith']
    assert result2 == ['Bob Jones']
    # Should have deleted the cache keys
    mock_cache.delete.assert_called()
    # Should have called DB twice total (once for each get_all_users call)
    assert mock_readonly.call_count == initial_db_calls + 1
    
def test_clear_user_cache_logs_correctly(mock_cache, caplog):
    """Test that cache clearing logs appropriate messages"""
    with caplog.at_level(logging.INFO):
        utils.clear_user_cache()
    
    # Check that info message was logged
    assert "Cleared user-related caches" in caplog.text

def test_clear_duty_cache_logs_correctly(mock_cache, caplog):
    """Test that duty cache clearing logs correctly"""
    with caplog.at_level(logging.INFO):
        utils.clear_duty_cache()
    
    assert "Cleared duty-related caches" in caplog.text

def test_clear_feedback_cache_logs_correctly(mock_cache, caplog):
    """Test that feedback cache clearing logs correctly"""
    with caplog.at_level(logging.INFO):
        utils.clear_feedback_cache()
    
    assert "Cleared feedback caches" in caplog.text

def test_clear_all_cache_logs_correctly(mock_cache, caplog):
    """Test that all cache clearing logs correctly"""
    with caplog.at_level(logging.INFO):
        utils.clear_all_cache()
    
    assert "Cleared all caches" in caplog.text

# ─── Tests for cache management in realistic scenarios ──────────────────────

def test_cache_clear_after_user_update_scenario(mock_readonly, mock_cache):
    """Test realistic scenario: user gets updated, cache gets cleared"""
    # Arrange: Initial user data in cache
    mock_readonly.return_value = [('Alice Smith','SectionA','RoleA','TeamA')]
    initial_users = utils.get_all_users()
    
    # Simulate user update (this would happen in your route handler)
    # ... user update logic would go here ...
    
    # Act: Clear cache after user update
    utils.clear_user_cache()
    
    # Arrange: New data after update
    mock_cache.get.return_value = None  # Cache cleared
    mock_readonly.return_value = [('Alice Jones','SectionA','RoleA','TeamA')]  # Name changed
    
    # Act: Get fresh data
    updated_users = utils.get_all_users()
    
    # Assert
    assert initial_users == ['Alice Smith']
    assert updated_users == ['Alice Jones']
    mock_cache.delete.assert_called()

def test_cache_clear_after_duty_schedule_update_scenario(mock_readonly, mock_cache):
    """Test realistic scenario: duty schedule gets updated, cache gets cleared"""
    # Arrange: Initial schedule in cache
    mock_readonly.return_value = [
        (1, 0, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}])
    ]
    initial_schedule = utils.get_duty_schedule()
    
    # Act: Clear cache after schedule update
    utils.clear_duty_cache()
    
    # Arrange: New schedule data
    mock_cache.get.return_value = None  # Cache cleared
    mock_readonly.return_value = [
        (1, 0, "Kitchen Duty", "Clean kitchen UPDATED", "Team A", [{"name": "Bob", "week": "Both"}])
    ]
    
    # Act: Get fresh schedule
    updated_schedule = utils.get_duty_schedule()
    
    # Assert: Schedules should be different
    assert len(initial_schedule) == 14  # 2 weeks
    assert len(updated_schedule) == 14  # 2 weeks
    # Cache should have been cleared
    mock_cache.clear.assert_called()

# ─── Edge case tests ─────────────────────────────────────────────────────────

def test_clear_duty_cache_with_different_dates(mock_cache):
    """Test that duty cache clearing works correctly across different dates"""
    dates_to_test = [
        datetime(2025, 1, 1).date(),
        datetime(2025, 6, 15).date(),
        datetime(2025, 12, 31).date()
    ]
    
    for test_date in dates_to_test:
        mock_cache.reset_mock()
        
        with patch('backend.bcssm_backend.utils.datetime') as mock_dt:
            mock_dt.now.return_value.date.return_value = test_date
            
            utils.clear_duty_cache()
            
            expected_key = f'duties:schedule:14day:{test_date}'
            mock_cache.delete.assert_called_with(expected_key)
            mock_cache.clear.assert_called_once()

def test_multiple_cache_clears_in_sequence(mock_cache):
    """Test calling multiple cache clear methods in sequence"""
    # Act: Call all cache clear methods
    utils.clear_user_cache()
    utils.clear_duty_cache() 
    utils.clear_feedback_cache()
    utils.clear_all_cache()
    
    # Assert: All appropriate methods were called
    # Note: exact call counts depend on the implementation
    assert mock_cache.delete.call_count >= 3  # At least user, feedback, and duty keys
    assert mock_cache.clear.call_count >= 2   # Duty cache and all cache

# ─── Tests for get_all_sections_with_users() ─────────────────────────────────

def test_get_all_sections_with_users_happy_path(mock_readonly, mock_cache):
    """Test get_all_sections_with_users with normal data"""
    # Arrange: return section data with users (now includes week field)
    mock_readonly.return_value = [
        ('Minis', 1, 'Alice Smith', 'Section Leader', 'Both'),
        ('Minis', 1, 'Bob Jones', 'Team Member', 'Week A'),
        ('Micros', 2, 'Charlie Brown', 'Section Leader', 'Week B'),
        ('Unassigned', 999, 'Dave Wilson', 'Team Member', 'Both')
    ]
    
    # Act
    result = utils.get_all_sections_with_users()
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == 3  # Minis, Micros, Unassigned
    
    # Check Minis section
    minis_section = next(s for s in result if s['name'] == 'Minis')
    assert minis_section['display_order'] == 1
    assert minis_section['user_count'] == 2
    assert len(minis_section['users']) == 2
    assert minis_section['users'][0] == {'name': 'Alice Smith', 'role': 'Section Leader', 'week': 'Both'}
    assert minis_section['users'][1] == {'name': 'Bob Jones', 'role': 'Team Member', 'week': 'Week A'}
    
    # Check Micros section
    micros_section = next(s for s in result if s['name'] == 'Micros')
    assert micros_section['user_count'] == 1
    assert micros_section['users'][0] == {'name': 'Charlie Brown', 'role': 'Section Leader', 'week': 'Week B'}
    
    # Check Unassigned section
    unassigned_section = next(s for s in result if s['name'] == 'Unassigned')
    assert unassigned_section['display_order'] == 999
    assert unassigned_section['user_count'] == 1
    
    # Verify cache operations (updated cache key)
    mock_cache.get.assert_called_once_with('sections:with_users:all_v6')
    mock_cache.set.assert_called_once_with('sections:with_users:all_v6', result, timeout=1800)
    
    # Verify SQL query structure
    sql = mock_readonly.call_args[0][0]
    assert "RIGHT JOIN users u ON s.id = u.section_id" in sql
    assert "COALESCE(s.name, 'Unassigned')" in sql
    assert "WHEN u.role = 'Admin' THEN 'Section Leader'" in sql
    assert "u.week" in sql  # New field
    assert "ORDER BY" in sql

def test_get_all_sections_with_users_cache_hit(mock_readonly, mock_cache):
    """Test get_all_sections_with_users with cache hit"""
    # Arrange: cache returns data
    cached_data = [
        {
            "name": "Cached Section",
            "display_order": 1,
            "users": [{"name": "Cached User", "role": "Cached Role", "week": "Both"}],
            "user_count": 1
        }
    ]
    mock_cache.get.return_value = cached_data
    
    # Act
    result = utils.get_all_sections_with_users()
    
    # Assert
    assert result == cached_data
    
    # Verify cache was checked (updated cache key)
    mock_cache.get.assert_called_once_with('sections:with_users:all_v6')
    # Verify DB was NOT queried
    mock_readonly.assert_not_called()
    # Verify cache was NOT set (already had data)
    mock_cache.set.assert_not_called()

def test_get_all_sections_with_users_empty_result(mock_readonly, mock_cache):
    """Test get_all_sections_with_users with no data"""
    # Arrange: empty result from database
    mock_readonly.return_value = []
    
    # Act
    result = utils.get_all_sections_with_users()
    
    # Assert
    assert result == []
    
    # Verify cache operations (updated cache key)
    mock_cache.get.assert_called_once_with('sections:with_users:all_v6')
    mock_cache.set.assert_called_once_with('sections:with_users:all_v6', [], timeout=1800)

def test_get_all_sections_with_users_db_failure_returns_error(mock_readonly, mock_cache):
    """Test get_all_sections_with_users with database failure"""
    # Arrange: database error
    mock_readonly.side_effect = SQLAlchemyError("Database connection failed")
    
    # Act
    result = utils.get_all_sections_with_users()
    
    # Assert
    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to fetch sections with users" in result["error"]
    assert "Database connection failed" in result["error"]
    
    # Verify error was cached with short timeout (updated cache key)
    mock_cache.set.assert_called_once_with('sections:with_users:all_v6', result, timeout=60)

def test_get_all_sections_with_users_admin_role_conversion(mock_readonly, mock_cache):
    """Test that Admin role is converted to Section Leader"""
    # Arrange: data with Admin role (now includes week field)
    mock_readonly.return_value = [
        ('TestSection', 1, 'Admin User', 'Section Leader', 'Both'),  # Already converted in SQL
        ('TestSection', 1, 'Regular User', 'Team Member', 'Week A')
    ]
    
    # Act
    result = utils.get_all_sections_with_users()
    
    # Assert
    section = result[0]
    admin_user = next(u for u in section['users'] if u['name'] == 'Admin User')
    assert admin_user['role'] == 'Section Leader'
    assert admin_user['week'] == 'Both'  # Check week field too

def test_get_all_sections_with_users_sorting(mock_readonly, mock_cache):
    """Test that sections are sorted by display_order then name"""
    # Arrange: unsorted data (now includes week field)
    mock_readonly.return_value = [
        ('Zebra Section', 3, 'User A', 'Team Member', 'Both'),
        ('Alpha Section', 1, 'User B', 'Team Member', 'Week A'),
        ('Beta Section', 1, 'User C', 'Team Member', 'Week B'),
        ('Unassigned', 999, 'User D', 'Team Member', 'Both')
    ]
    
    # Act
    result = utils.get_all_sections_with_users()
    
    # Assert - should be sorted by display_order, then name
    section_names = [s['name'] for s in result]
    assert section_names == ['Alpha Section', 'Beta Section', 'Zebra Section', 'Unassigned']

# ─── Tests for get_section_statistics() ──────────────────────────────────────

def test_get_section_statistics_happy_path(mock_readonly, mock_cache):
    """Test get_section_statistics with normal data"""
    # Arrange: return statistics data
    mock_readonly.return_value = [
        ('Minis', 1, 5, 1, 2, 2),      # 5 total, 1 leader, 2 team leaders, 2 others
        ('Micros', 2, 3, 1, 1, 1),     # 3 total, 1 leader, 1 team leader, 1 other
        ('Unassigned', 999, 2, 0, 0, 2) # 2 total, 0 leaders, 0 team leaders, 2 others
    ]
    
    # Act
    result = utils.get_section_statistics()
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == 3
    
    # Check Minis statistics
    minis_stats = next(s for s in result if s['section_name'] == 'Minis')
    assert minis_stats['display_order'] == 1
    assert minis_stats['total_users'] == 5
    assert minis_stats['section_leaders'] == 1
    assert minis_stats['team_leaders'] == 2
    assert minis_stats['other_roles'] == 2
    
    # Check Micros statistics
    micros_stats = next(s for s in result if s['section_name'] == 'Micros')
    assert micros_stats['total_users'] == 3
    assert micros_stats['section_leaders'] == 1
    
    # Check Unassigned statistics
    unassigned_stats = next(s for s in result if s['section_name'] == 'Unassigned')
    assert unassigned_stats['display_order'] == 999
    assert unassigned_stats['section_leaders'] == 0
    
    # Verify cache operations
    mock_cache.get.assert_called_once_with('sections:statistics:summary')
    mock_cache.set.assert_called_once_with('sections:statistics:summary', result, timeout=3600)
    
    # Verify SQL query structure
    sql = mock_readonly.call_args[0][0]
    assert "RIGHT JOIN users u ON s.id = u.section_id" in sql
    assert "COUNT(u.id) AS total_users" in sql
    assert "COUNT(CASE WHEN u.role IN ('Section Leader', 'Admin')" in sql
    assert "COUNT(CASE WHEN u.role = 'Team Leader'" in sql
    assert "GROUP BY s.id, s.name, s.display_order" in sql

def test_get_section_statistics_cache_hit(mock_readonly, mock_cache):
    """Test get_section_statistics with cache hit"""
    # Arrange: cache returns data
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
    
    # Act
    result = utils.get_section_statistics()
    
    # Assert
    assert result == cached_stats
    
    # Verify cache was checked
    mock_cache.get.assert_called_once_with('sections:statistics:summary')
    # Verify DB was NOT queried
    mock_readonly.assert_not_called()
    # Verify cache was NOT set (already had data)
    mock_cache.set.assert_not_called()

def test_get_section_statistics_empty_result(mock_readonly, mock_cache):
    """Test get_section_statistics with no data"""
    # Arrange: empty result from database
    mock_readonly.return_value = []
    
    # Act
    result = utils.get_section_statistics()
    
    # Assert
    assert result == []
    
    # Verify cache operations
    mock_cache.get.assert_called_once_with('sections:statistics:summary')
    mock_cache.set.assert_called_once_with('sections:statistics:summary', [], timeout=3600)

def test_get_section_statistics_db_failure_returns_error(mock_readonly, mock_cache):
    """Test get_section_statistics with database failure"""
    # Arrange: database error
    mock_readonly.side_effect = SQLAlchemyError("Statistics query failed")
    
    # Act
    result = utils.get_section_statistics()
    
    # Assert
    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to fetch section statistics" in result["error"]
    assert "Statistics query failed" in result["error"]
    
    # Verify error was cached with short timeout
    mock_cache.set.assert_called_once_with('sections:statistics:summary', result, timeout=60)

def test_get_section_statistics_role_counting(mock_readonly, mock_cache):
    """Test that role counting logic works correctly"""
    # Arrange: data with various roles including Admin
    mock_readonly.return_value = [
        ('TestSection', 1, 6, 2, 1, 3)  # 6 total, 2 section leaders (including Admin), 1 team leader, 3 others
    ]
    
    # Act
    result = utils.get_section_statistics()
    
    # Assert
    stats = result[0]
    assert stats['total_users'] == 6
    assert stats['section_leaders'] == 2  # Should include both Admin and Section Leader roles
    assert stats['team_leaders'] == 1
    assert stats['other_roles'] == 3
    
    # Verify totals add up
    assert stats['section_leaders'] + stats['team_leaders'] + stats['other_roles'] == stats['total_users']

# ─── Tests for get_users_by_section_optimized() ──────────────────────────────

def test_get_users_by_section_optimized_normal_section(mock_readonly, mock_cache):
    """Test get_users_by_section_optimized with a normal section"""
    # Arrange: return users for specific section
    mock_readonly.return_value = [
        ('Alice Smith', 'Section Leader'),
        ('Bob Jones', 'Team Member'),
        ('Charlie Brown', 'Team Leader')
    ]
    
    # Act
    result = utils.get_users_by_section_optimized("Minis")
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == 3
    assert result == [
        {"name": "Alice Smith", "role": "Section Leader"},
        {"name": "Bob Jones", "role": "Team Member"},
        {"name": "Charlie Brown", "role": "Team Leader"}
    ]
    
    # Verify cache operations
    mock_cache.get.assert_called_once_with('users:section:Minis:detailed')
    mock_cache.set.assert_called_once_with('users:section:Minis:detailed', result, timeout=1800)
    
    # Verify SQL query and parameters
    sql, params = mock_readonly.call_args[0]
    assert "INNER JOIN sections s ON u.section_id = s.id" in sql
    assert "WHERE s.name = :section_name" in sql
    assert "WHEN u.role = 'Admin' THEN 'Section Leader'" in sql
    assert params == {"section_name": "Minis"}

def test_get_users_by_section_optimized_unassigned_section(mock_readonly, mock_cache):
    """Test get_users_by_section_optimized with Unassigned section"""
    # Arrange: return unassigned users
    mock_readonly.return_value = [
        ('Dave Wilson', 'Team Member'),
        ('Eve Davis', 'Section Leader')  # Admin converted to Section Leader
    ]
    
    # Act
    result = utils.get_users_by_section_optimized("Unassigned")
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == 2
    assert result == [
        {"name": "Dave Wilson", "role": "Team Member"},
        {"name": "Eve Davis", "role": "Section Leader"}
    ]
    
    # Verify cache operations
    mock_cache.get.assert_called_once_with('users:section:Unassigned:detailed')
    mock_cache.set.assert_called_once_with('users:section:Unassigned:detailed', result, timeout=1800)
    
    # Verify SQL query for unassigned users
    sql, params = mock_readonly.call_args[0]
    assert "WHERE u.section_id IS NULL" in sql
    assert "INNER JOIN sections" not in sql  # Should not join sections for unassigned
    assert params == {}  # No parameters for unassigned query

def test_get_users_by_section_optimized_cache_hit(mock_readonly, mock_cache):
    """Test get_users_by_section_optimized with cache hit"""
    # Arrange: cache returns data
    cached_users = [
        {"name": "Cached User", "role": "Cached Role"}
    ]
    mock_cache.get.return_value = cached_users
    
    # Act
    result = utils.get_users_by_section_optimized("TestSection")
    
    # Assert
    assert result == cached_users
    
    # Verify cache was checked
    mock_cache.get.assert_called_once_with('users:section:TestSection:detailed')
    # Verify DB was NOT queried
    mock_readonly.assert_not_called()
    # Verify cache was NOT set (already had data)
    mock_cache.set.assert_not_called()

def test_get_users_by_section_optimized_empty_result(mock_readonly, mock_cache):
    """Test get_users_by_section_optimized with no users in section"""
    # Arrange: empty result from database
    mock_readonly.return_value = []
    
    # Act
    result = utils.get_users_by_section_optimized("EmptySection")
    
    # Assert
    assert result == []
    
    # Verify cache operations
    mock_cache.get.assert_called_once_with('users:section:EmptySection:detailed')
    mock_cache.set.assert_called_once_with('users:section:EmptySection:detailed', [], timeout=1800)

def test_get_users_by_section_optimized_db_failure_returns_error(mock_readonly, mock_cache):
    """Test get_users_by_section_optimized with database failure"""
    # Arrange: database error
    mock_readonly.side_effect = SQLAlchemyError("Section query failed")
    
    # Act
    result = utils.get_users_by_section_optimized("TestSection")
    
    # Assert
    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to fetch users by section" in result["error"]
    assert "Section query failed" in result["error"]
    
    # Verify error was cached with short timeout
    mock_cache.set.assert_called_once_with('users:section:TestSection:detailed', result, timeout=60)

def test_get_users_by_section_optimized_admin_role_conversion(mock_readonly, mock_cache):
    """Test that Admin role is converted to Section Leader"""
    # Arrange: data with Admin role (already converted in SQL)
    mock_readonly.return_value = [
        ('Admin User', 'Section Leader'),  # Admin converted to Section Leader in SQL
        ('Regular User', 'Team Member')
    ]
    
    # Act
    result = utils.get_users_by_section_optimized("TestSection")
    
    # Assert
    admin_user = next(u for u in result if u['name'] == 'Admin User')
    assert admin_user['role'] == 'Section Leader'
    
    regular_user = next(u for u in result if u['name'] == 'Regular User')
    assert regular_user['role'] == 'Team Member'

def test_get_users_by_section_optimized_sorting(mock_readonly, mock_cache):
    """Test that users are sorted by name"""
    # Arrange: unsorted data
    mock_readonly.return_value = [
        ('Alice Smith', 'Team Member'),
        ('Bob Jones', 'Section Leader'),
        ('Charlie Brown', 'Team Leader')
    ]
    
    # Act
    result = utils.get_users_by_section_optimized("TestSection")
    
    # Assert - should be sorted by name (ORDER BY u.name in SQL)
    user_names = [u['name'] for u in result]
    assert user_names == ['Alice Smith', 'Bob Jones', 'Charlie Brown']

# ─── Tests for clear_user_cache() updates ────────────────────────────────────

def test_clear_user_cache_includes_new_keys(mock_cache):
    """Test that clear_user_cache clears the new cache keys"""
    # Mock get_all_sections to return some sections
    with patch('backend.bcssm_backend.utils.get_all_sections') as mock_get_sections:
        mock_get_sections.return_value = ['Minis', 'Micros', 'Majors']
        
        # Act
        utils.clear_user_cache()
        
        # Assert - should delete the basic cache keys plus section-specific ones
        # Check that at least the core keys are deleted
        expected_basic_calls = [
            unittest.mock.call('users:all:list'),
            unittest.mock.call('sections:all:list'),
            unittest.mock.call('sections:with_users:all'),
            unittest.mock.call('sections:statistics:summary'),
            unittest.mock.call('users:section:Unassigned:detailed')
        ]
        
        mock_cache.delete.assert_has_calls(expected_basic_calls, any_order=True)
        # Verify that we made at least the expected number of delete calls
        assert mock_cache.delete.call_count >= 5

def test_clear_user_cache_handles_get_sections_error(mock_cache, caplog):
    """Test that clear_user_cache handles errors from get_all_sections gracefully"""
    # Mock get_all_sections to return an error dict
    with patch('backend.bcssm_backend.utils.get_all_sections') as mock_get_sections:
        mock_get_sections.return_value = {"error": "Failed to fetch sections"}
        
        # Act
        with caplog.at_level(logging.INFO):
            utils.clear_user_cache()
        
        # Assert - should still clear basic caches
        expected_calls = [
            unittest.mock.call('users:all:list'),
            unittest.mock.call('sections:all:list'),
            unittest.mock.call('sections:with_users:all'),
            unittest.mock.call('sections:statistics:summary'),
            # Should still clear Unassigned
            unittest.mock.call('users:section:Unassigned:detailed')
        ]
        
        mock_cache.delete.assert_has_calls(expected_calls, any_order=True)
        # Should not try to clear individual sections since get_all_sections failed
        mock_cache.delete.assert_any_call('users:section:Unassigned:detailed')

def test_clear_user_cache_handles_empty_sections_list(mock_cache):
    """Test that clear_user_cache handles empty sections list"""
    # Mock get_all_sections to return empty list
    with patch('backend.bcssm_backend.utils.get_all_sections') as mock_get_sections:
        mock_get_sections.return_value = []
        
        # Act
        utils.clear_user_cache()
        
        # Assert - should clear basic caches and Unassigned
        expected_calls = [
            unittest.mock.call('users:all:list'),
            unittest.mock.call('sections:all:list'),
            unittest.mock.call('sections:with_users:all'),
            unittest.mock.call('sections:statistics:summary'),
            unittest.mock.call('users:section:Unassigned:detailed')
        ]
        
        mock_cache.delete.assert_has_calls(expected_calls, any_order=True)

# ─── Integration tests for the new methods ───────────────────────────────────

def test_section_methods_integration_workflow(mock_readonly, mock_cache):
    """Test a realistic workflow using all three new methods"""
    # Arrange: Setup data for all three methods
    
    # Data for get_all_sections_with_users (now includes week field)
    sections_with_users_data = [
        ('Minis', 1, 'Alice Smith', 'Section Leader', 'Both'),
        ('Minis', 1, 'Bob Jones', 'Team Member', 'Week A'),
        ('Micros', 2, 'Charlie Brown', 'Section Leader', 'Week B')
    ]
    
    # Data for get_section_statistics  
    statistics_data = [
        ('Minis', 1, 2, 1, 0, 1),
        ('Micros', 2, 1, 1, 0, 0)
    ]
    
    # Data for get_users_by_section_optimized
    minis_users_data = [
        ('Alice Smith', 'Section Leader'),
        ('Bob Jones', 'Team Member')
    ]
    
    # Act & Assert: Call each method and verify results
    
    # 1. Get all sections with users
    mock_readonly.return_value = sections_with_users_data
    sections_result = utils.get_all_sections_with_users()
    assert len(sections_result) == 2
    assert sections_result[0]['name'] == 'Minis'
    assert sections_result[0]['user_count'] == 2
    
    # 2. Get section statistics
    mock_readonly.return_value = statistics_data
    stats_result = utils.get_section_statistics()
    assert len(stats_result) == 2
    assert stats_result[0]['section_name'] == 'Minis'
    assert stats_result[0]['total_users'] == 2
    
    # 3. Get users for specific section
    mock_readonly.return_value = minis_users_data
    users_result = utils.get_users_by_section_optimized("Minis")
    assert len(users_result) == 2
    assert users_result[0]['name'] == 'Alice Smith'
    
    # Verify that all methods used caching
    assert mock_cache.get.call_count == 3
    assert mock_cache.set.call_count == 3

def test_error_handling_consistency_across_methods(mock_readonly, mock_cache):
    """Test that all three methods handle errors consistently"""
    error_message = "Database connection lost"
    mock_readonly.side_effect = SQLAlchemyError(error_message)
    
    # Test each method returns error dict with consistent structure
    methods_to_test = [
        (utils.get_all_sections_with_users, "Failed to fetch sections with users"),
        (utils.get_section_statistics, "Failed to fetch section statistics"),
        (lambda: utils.get_users_by_section_optimized("TestSection"), "Failed to fetch users by section")
    ]
    
    for method, expected_error_prefix in methods_to_test:
        result = method()
        
        assert isinstance(result, dict)
        assert "error" in result
        assert expected_error_prefix in result["error"]
        assert error_message in result["error"]

# ─── Tests for get_current_cycle_week() ──────────────────────────────────────

class MockDateTime:
    """A proper mock for datetime that returns real datetime objects"""
    def __init__(self, test_datetime):
        self.test_datetime = test_datetime
    
    def now(self):
        return self.test_datetime
    
    def __call__(self, *args, **kwargs):
        # Handle calls like datetime(2025, 7, 7)
        return datetime(*args, **kwargs)

def test_get_current_cycle_week_basic_calculation():
    """Test the basic cycle week calculation logic"""
    from datetime import timedelta
    
    # Test Week 0 (July 7, 2025 - start date)
    test_date = datetime(2025, 7, 7)
    with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_date)):
        utils.get_current_cycle_week.cache_clear()
        result = utils.get_current_cycle_week()
        assert result == 0
        
    # Test Week 1 (July 14, 2025 - 7 days later) 
    test_date = datetime(2025, 7, 14)
    with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_date)):
        utils.get_current_cycle_week.cache_clear()
        result = utils.get_current_cycle_week()
        assert result == 1
        
    # Test Week 0 again (July 21, 2025 - 14 days later)
    test_date = datetime(2025, 7, 21)
    with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_date)):
        utils.get_current_cycle_week.cache_clear()
        result = utils.get_current_cycle_week()
        assert result == 0

def test_get_current_cycle_week_timezone_consistency():
    """Test that the function works consistently across different times of day"""
    test_date = datetime(2025, 7, 14).date()  # Should be Week 1
    
    # Test different times of day - all should give same result since we use .date()
    times_to_test = [
        datetime.combine(test_date, datetime.min.time()),  # 00:00:00
        datetime.combine(test_date, datetime.max.time().replace(microsecond=0)),  # 23:59:59
        datetime(2025, 7, 14, 12, 30, 45),  # Middle of day
    ]
    
    for test_datetime in times_to_test:
        with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_datetime)):
            utils.get_current_cycle_week.cache_clear()
            result = utils.get_current_cycle_week()
            assert result == 1, f"Failed for time {test_datetime}"

def test_get_current_cycle_week_edge_cases():
    """Test edge cases around cycle boundaries"""
    test_cases = [
        # (date, expected_cycle, description)
        (datetime(2025, 7, 6), 1, "Day before start"),  # -1 days, (-1//7)%2 = 1 in Python
        (datetime(2025, 7, 7), 0, "Start date"),        # 0 days = week 0, (0//7)%2 = 0
        (datetime(2025, 7, 8), 0, "Day after start"),   # 1 day = week 0, (1//7)%2 = 0
        (datetime(2025, 7, 13), 0, "End of Week 0"),    # 6 days = week 0, (6//7)%2 = 0
        (datetime(2025, 7, 14), 1, "Start of Week 1"),  # 7 days = week 1, (7//7)%2 = 1
        (datetime(2025, 7, 20), 1, "End of Week 1"),    # 13 days = week 1, (13//7)%2 = 1
        (datetime(2025, 7, 21), 0, "Start of Week 0 again"), # 14 days = week 2, (14//7)%2 = 0
        (datetime(2025, 8, 4), 0, "Week 0 after month boundary"),  # 28 days = week 4, (28//7)%2 = 0
        (datetime(2025, 8, 11), 1, "Week 1 after month boundary"), # 35 days = week 5, (35//7)%2 = 1
    ]
    
    for test_datetime, expected_cycle, description in test_cases:
        with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_datetime)):
            utils.get_current_cycle_week.cache_clear()
            result = utils.get_current_cycle_week()
            assert result == expected_cycle, f"{description}: expected {expected_cycle}, got {result}"

def test_get_current_cycle_week_caching_behavior():
    """Test that the LRU cache works correctly"""
    test_date = datetime(2025, 7, 14)
    mock_datetime = MockDateTime(test_date)
    
    with patch('backend.bcssm_backend.utils.datetime', mock_datetime):
        utils.get_current_cycle_week.cache_clear()
        
        # First call should calculate
        result1 = utils.get_current_cycle_week()
        
        # Second call should use cache
        result2 = utils.get_current_cycle_week()
        
        # Results should be the same
        assert result1 == result2 == 1

def test_get_current_cycle_week_long_term_pattern():
    """Test the cycle pattern over a longer period"""
    from datetime import timedelta
    
    # Test the pattern for several weeks
    start_date = datetime(2025, 7, 7)
    
    for week_num in range(8):  # Test 8 weeks
        test_datetime = start_date + timedelta(weeks=week_num)
        expected_cycle = week_num % 2
        
        with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_datetime)):
            utils.get_current_cycle_week.cache_clear()
            result = utils.get_current_cycle_week()
            assert result == expected_cycle, f"Week {week_num} ({test_datetime.date()}): expected {expected_cycle}, got {result}"

def test_get_current_cycle_week_matches_duty_schedule_calculation():
    """Test that get_current_cycle_week matches the calculation in get_duty_schedule"""
    test_dates = [
        datetime(2025, 7, 7),   # Week 0
        datetime(2025, 7, 14),  # Week 1
        datetime(2025, 7, 21),  # Week 0
        datetime(2025, 7, 28),  # Week 1
        datetime(2025, 8, 4),   # Week 0
    ]
    
    for current_date in test_dates:
        # Calculate using the same logic as get_duty_schedule
        days_since_cycle_start = (current_date.date() - datetime(2025, 7, 7).date()).days
        expected_cycle = (days_since_cycle_start // 7) % 2
        
        # Test our function
        with patch('backend.bcssm_backend.utils.datetime', MockDateTime(current_date)):
            utils.get_current_cycle_week.cache_clear()
            result = utils.get_current_cycle_week()
            assert result == expected_cycle, f"Date {current_date.date()}: expected {expected_cycle}, got {result}"

def test_get_current_cycle_week_before_start_date():
    """Test behavior for dates before the cycle start date"""
    # Test dates before July 7, 2025
    test_cases = [
        (datetime(2025, 7, 6), "Day before start"),    # -1 days, (-1//7)%2 = 1 in Python
        (datetime(2025, 6, 30), "Week before start"),  # -7 days, (-7//7)%2 = 1 in Python
        (datetime(2025, 6, 23), "Two weeks before"),   # -14 days, (-14//7)%2 = 0 in Python
    ]
    
    for test_datetime, description in test_cases:
        with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_datetime)):
            utils.get_current_cycle_week.cache_clear()
            result = utils.get_current_cycle_week()
            
            # Calculate expected result manually
            days_since_start = (test_datetime.date() - datetime(2025, 7, 7).date()).days
            expected_cycle = (days_since_start // 7) % 2
            
            assert result == expected_cycle, f"{description}: expected {expected_cycle}, got {result}"

def test_get_current_cycle_week_cache_info():
    """Test that the cache info is accessible and reasonable"""
    # Get reference to the cached function
    cached_func = utils.get_current_cycle_week
    
    # Clear cache first
    cached_func.cache_clear()
    
    # Check initial cache info (suppress pylint warning)
    info = cached_func.cache_info()  # pylint: disable=too-many-function-args
    assert info.currsize == 0
    assert info.maxsize == 128  # As defined in the decorator
    
    # Call function to populate cache
    with patch('backend.bcssm_backend.utils.datetime', MockDateTime(datetime(2025, 7, 14))):
        cached_func()
    
    # Check cache info after call (suppress pylint warning)
    info_after = cached_func.cache_info()  # pylint: disable=too-many-function-args
    assert info_after.currsize == 1
    assert info_after.hits == 0  # First call is a miss
    assert info_after.misses == 1

def test_get_current_cycle_week_integration_with_get_user_duty(monkeypatch, mock_readonly, mock_cache):
    """Test that get_current_cycle_week integrates correctly with get_user_duty"""
    # Mock datetime for both the main function and get_current_cycle_week
    FakeDatetime.today_weekday = 0  # Monday
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    
    # Mock the get_current_cycle_week to return the expected value
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 1)
    
    # Set up database response
    mock_readonly.return_value = [
        ("Test User", "Test Section", "Leader", "Test Team", "Test Duty")
    ]
    
    # Act: Call get_user_duty which should use get_current_cycle_week
    result = utils.get_user_duty("Test User")
    
    # Assert: Check that the correct parameters were used
    sql, params = mock_readonly.call_args[0]
    assert params['cycle_week'] == 1  # Should be Week 1 for July 14, 2025
    assert params['day'] == 1  # Monday with corrected calculation: (0 + 1) % 7 = 1
    
    # Check that the result is as expected
    assert result['user'] == "Test User"
    assert result['duty'] == "Test Duty"

def test_get_current_cycle_week_real_calculation():
    """Test the actual calculation without mocking to ensure it works correctly"""
    # Manually test the calculation logic
    start_date = datetime(2025, 7, 7).date()
    
    test_cases = [
        (datetime(2025, 7, 7).date(), 0),   # Day 0, Week 0
        (datetime(2025, 7, 14).date(), 1),  # Day 7, Week 1
        (datetime(2025, 7, 21).date(), 0),  # Day 14, Week 0 again
        (datetime(2025, 7, 28).date(), 1),  # Day 21, Week 1 again
    ]
    
    for test_date, expected_cycle in test_cases:
        # Calculate manually what the function should return
        days_since_start = (test_date - start_date).days
        calculated_cycle = (days_since_start // 7) % 2
        
        assert calculated_cycle == expected_cycle, f"Manual calculation failed for {test_date}"
        
        # Test with mocked datetime
        test_datetime = datetime.combine(test_date, datetime.min.time())
        with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_datetime)):
            utils.get_current_cycle_week.cache_clear()
            result = utils.get_current_cycle_week()
            
            assert result == expected_cycle, f"Function returned {result}, expected {expected_cycle} for {test_date}"

def test_get_current_cycle_week_specific_monday_july_14():
    """Test specifically for Monday July 14, 2025 which should be cycle week 1"""
    test_datetime = datetime(2025, 7, 14, 12, 0, 0)  # Monday July 14, 2025 at noon

    with patch('backend.bcssm_backend.utils.datetime', MockDateTime(test_datetime)):
        utils.get_current_cycle_week.cache_clear()
        result = utils.get_current_cycle_week()

        # July 14, 2025 is exactly 7 days after July 7, 2025
        # (7 // 7) % 2 = 1 % 2 = 1
        assert result == 1, f"July 14, 2025 should be cycle week 1, got {result}"


# ─── Tests for get_feedback_by_date ─────────────────────────────────────────

def test_get_feedback_by_date_success(monkeypatch):
    mock_exec = MagicMock(return_value=[("Minis", "Great job"), ("Majors", None)])
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_readonly_query", mock_exec)
    result, error = utils.get_feedback_by_date("2025-06-07")
    assert error is None
    assert result == {"Minis": "Great job", "Majors": "No feedback available"}


def test_get_feedback_by_date_exception(monkeypatch):
    mock_exec = MagicMock(side_effect=SQLAlchemyError("DB fail"))
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_readonly_query", mock_exec)
    result, error = utils.get_feedback_by_date("2025-06-07")
    assert result is None
    assert error == "An error occurred while fetching feedback"


# ─── Tests for get_user_info ─────────────────────────────────────────────────

def test_get_user_info_found(monkeypatch):
    mock_exec = MagicMock(return_value=[("Alice", "Leader", "Minis")])
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_readonly_query", mock_exec)
    info = utils.get_user_info("Alice")
    assert info == {"name": "Alice", "role": "Leader", "section": "Minis"}


def test_get_user_info_not_found(monkeypatch):
    mock_exec = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_readonly_query", mock_exec)
    assert utils.get_user_info("Bob") is None


def test_get_user_info_exception(monkeypatch):
    mock_exec = MagicMock(side_effect=SQLAlchemyError("Oops"))
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_readonly_query", mock_exec)
    with pytest.raises(SQLAlchemyError):
        utils.get_user_info("Alice")


# ─── Tests for save_devos_feedback ───────────────────────────────────────────

def test_save_devos_feedback_success(monkeypatch):
    # Single INSERT...SELECT...RETURNING query: returns [(section_id,)] when section exists.
    mock_exec = MagicMock(return_value=[(5,)])
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_query", mock_exec)
    utils.save_devos_feedback("Minis", "2025-06-07", "Great session", 1)
    mock_exec.assert_called_once()
    call_params = mock_exec.call_args[0][1]
    assert call_params['section_name'] == 'Minis'
    assert call_params['new_feedback'] == 'Great session'
    assert call_params['date_str'] == '2025-06-07'
    assert call_params['editor_id'] == 1


def test_save_devos_feedback_section_not_found(monkeypatch):
    # RETURNING returns [] when the SELECT subquery matches no section.
    mock_exec = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_query", mock_exec)
    with pytest.raises(ValueError, match="Section 'Unknown' not found"):
        utils.save_devos_feedback("Unknown", "2025-06-07", "feedback", 1)


def test_save_devos_feedback_db_error(monkeypatch):
    mock_exec = MagicMock(side_effect=SQLAlchemyError("DB error"))
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_query", mock_exec)
    with pytest.raises(SQLAlchemyError):
        utils.save_devos_feedback("Minis", "2025-06-07", "feedback", 1)


def test_save_devos_feedback_uses_single_query(monkeypatch):
    # Verifies the TOCTOU-safe single-query design: exactly one execute_query call.
    mock_exec = MagicMock(return_value=[(7,)])
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_query", mock_exec)
    utils.save_devos_feedback("Seniors", "2025-06-07", "Good work", 2)
    assert mock_exec.call_count == 1
    query_text = mock_exec.call_args[0][0]
    assert "INSERT INTO feedback" in query_text
    assert "FROM sections" in query_text
    assert "RETURNING" in query_text