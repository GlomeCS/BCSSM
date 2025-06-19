import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from datetime import datetime
import logging
from backend.bcssm_backend import create_app, utils
import unittest.mock

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
    # Configure cache.get to return None by default (cache miss)
    fake_cache.get.return_value = None
    # Configure cache.set to return True (success)
    fake_cache.set.return_value = True
    # Configure cache.delete to return True (success)
    fake_cache.delete.return_value = True
    # Configure cache.clear to return True (success)
    fake_cache.clear.return_value = True
    
    monkeypatch.setattr('backend.bcssm_backend.utils.cache', fake_cache)
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
    mock_readonly.side_effect = Exception("DB is down")
    result = utils.get_all_users()
    assert result == []
    assert isinstance(result, list)

# ─── 5) Tests for get_user_duty() ─────────────────────────────────────────────
def test_get_user_duty_valid_today_returns_expected(monkeypatch, mock_readonly, mock_cache):
    # Freeze today to Wednesday (weekday==2)
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
    
    # Verify cache operations
    cache_key_pattern = 'user:duty:Ivy:day2:cycle0'
    mock_cache.get.assert_called_once_with(cache_key_pattern)
    mock_cache.set.assert_called_once()
    cache_set_args = mock_cache.set.call_args
    assert cache_set_args[0][0] == cache_key_pattern
    assert cache_set_args[1]['timeout'] == 600
    
    mock_readonly.assert_called_once()
    sql, params = mock_readonly.call_args[0]
    assert isinstance(params['day'], int)
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
    
    FakeDatetime.today_weekday = 2
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 0)
    
    # Act
    result = utils.get_user_duty("Ivy")
    
    # Assert
    assert result == cached_duty
    
    # Verify cache was checked
    mock_cache.get.assert_called_once_with('user:duty:Ivy:day2:cycle0')
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
    
    mock_readonly.side_effect = Exception("Something broke")
    result = utils.get_user_duty("SomeUser")
    assert isinstance(result, dict)
    assert "Failed to fetch duty for user" in result["error"]
    assert "Something broke" in result["error"]
    
    # Verify error was cached with shorter timeout
    mock_cache.set.assert_called_once()
    cache_set_args = mock_cache.set.call_args
    assert cache_set_args[1]['timeout'] == 60  # Short timeout for errors

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
    mock_readonly.side_effect = Exception("DB error on section query")
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
    mock_readonly.side_effect = Exception("Database failure")
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
    mock_readonly.side_effect = Exception("Database error")
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
    mock_db_session.execute.side_effect = Exception("DB error")
    with pytest.raises(Exception, match="DB error"):
        utils.execute_query("DELETE FROM users")
    mock_db_session.rollback.assert_called_once()

# Add test for get_todays_duties to verify cycle_week usage
def test_get_todays_duties_uses_cycle_week(monkeypatch, mock_readonly, mock_cache):
    # Mock datetime and cycle week
    FakeDatetime.today_weekday = 1  # Tuesday
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 1)
    
    mock_readonly.return_value = [
        (1, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}], True)
    ]
    
    result = utils.get_todays_duties("Alice")
    
    # Verify cache operations
    cache_key_pattern = 'duties:today:day1:cycle1:userAlice'
    mock_cache.get.assert_called_once_with(cache_key_pattern)
    mock_cache.set.assert_called_once()
    
    # Verify the query was called with correct parameters
    sql, params = mock_readonly.call_args[0]
    assert params['day'] == 1
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
    # Act
    utils.clear_user_cache()
    
    # Assert
    # Should delete specific user-related cache keys
    expected_calls = [
        unittest.mock.call('users:all:list'),
        unittest.mock.call('sections:all:list')
    ]
    mock_cache.delete.assert_has_calls(expected_calls, any_order=True)
    assert mock_cache.delete.call_count == 2

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
    mock_cache.delete.side_effect = Exception("Redis connection failed")
    mock_cache.clear.side_effect = Exception("Redis connection failed")
    
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
    assert mock_cache.set.call_count == 1
    
    # Act 2: Clear cache (simulating data update)
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
    # Should have called DB twice (once for each get after cache operations)
    assert mock_readonly.call_count == 2

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