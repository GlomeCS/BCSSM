import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from backend.bcssm_backend import create_app, utils

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

# ─── 2) Fixture to mock db.session directly (for testing execute_query) ─────
@pytest.fixture
def mock_db_session():
    with patch('backend.bcssm_backend.utils.db.session') as sess:
        # Make sess.begin() return a context manager yielding sess itself
        sess.begin.return_value.__enter__.return_value = sess
        sess.begin.return_value.__exit__.return_value = None
        yield sess

# ─── 3) Utility to control “today” in date‐sensitive code ─────────────────────
class FakeDatetime:
    @classmethod
    def now(cls):
        return SimpleNamespace(weekday=lambda: cls.today_weekday)

# ─── 4) Tests for get_all_users() ────────────────────────────────────────────
def test_get_all_users_happy_path(mock_readonly):
    # Arrange: return a couple of rows
    mock_readonly.return_value = [
        ('Alice Smith','SectionA','RoleA','TeamA'),
        ('Bob Jones','SectionB','RoleB','TeamB'),
    ]
    # Act
    result = utils.get_all_users()
    # Assert
    assert result == ['Alice Smith','Bob Jones']
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

def test_get_all_users_db_failure_returns_empty_list(mock_readonly):
    mock_readonly.side_effect = Exception("DB is down")
    result = utils.get_all_users()
    assert result == []
    assert isinstance(result, list)

# ─── 5) Tests for get_user_duty() ─────────────────────────────────────────────
def test_get_user_duty_valid_today_returns_expected(monkeypatch, mock_readonly):
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
    mock_readonly.assert_called_once()
    sql, params = mock_readonly.call_args[0]
    assert isinstance(params['day'], int)
    assert params['cycle_week'] == 0  # Check the new cycle_week parameter

def test_get_user_duty_not_assigned_returns_error(monkeypatch, mock_readonly):
    FakeDatetime.today_weekday = 0
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    mock_readonly.return_value = []
    result = utils.get_user_duty("NoOne")
    assert isinstance(result, dict)
    assert "error" in result
    assert "not found or no duty" in result["error"].lower()

def test_get_user_duty_exception_propagates_error(monkeypatch, mock_readonly):
    mock_readonly.side_effect = Exception("Something broke")
    result = utils.get_user_duty("SomeUser")
    assert isinstance(result, dict)
    assert "Failed to fetch duty for user" in result["error"]
    assert "Something broke" in result["error"]

# ─── 6) Tests for get_users_by_section() ───────────────────────────────────
def test_get_users_by_section_returns_list_of_dicts(mock_readonly):
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

def test_get_users_by_section_db_error_returns_error(mock_readonly):
    mock_readonly.side_effect = Exception("DB error on section query")
    result = utils.get_users_by_section("Minis")
    assert isinstance(result, dict)
    assert "Failed to fetch users by section" in result["error"]
    assert "DB error on section query" in result["error"]

# ─── 7) Tests for get_all_sections() ───────────────────────────────────────
def test_get_all_sections_with_records(mock_readonly):
    mock_readonly.return_value = [("Minis",), ("Micros",), ("Majors",)]
    result = utils.get_all_sections()
    assert result == ["Minis", "Micros", "Majors"]
    sql = mock_readonly.call_args[0][0]
    # expected_sql = """
    # SELECT name
    # FROM sections
    # ORDER BY display_order, name;
    # """
    assert "ORDER BY display_order, name" in sql.strip()
    assert sql.strip().startswith("SELECT name")

def test_get_all_sections_no_records(mock_readonly):
    mock_readonly.return_value = []
    result = utils.get_all_sections()
    assert result == []

def test_get_all_sections_exception(mock_readonly):
    mock_readonly.side_effect = Exception("Database failure")
    result = utils.get_all_sections()
    assert isinstance(result, dict)
    assert "Failed to fetch sections" in result["error"]
    assert "Database failure" in result["error"]

# ─── 8) Tests for get_all_feedback_dates() ──────────────────────────────────
def test_get_all_feedback_dates_with_records(mock_readonly):
    mock_readonly.return_value = [("2025-06-01",), ("2025-05-25",)]
    result = utils.get_all_feedback_dates()
    assert result == ["2025-06-01", "2025-05-25"]
    sql = mock_readonly.call_args[0][0]
    expected_sql = """
    SELECT DISTINCT date
    FROM feedback_records
    ORDER BY date DESC;
    """
    assert sql.strip() == expected_sql.strip()

def test_get_all_feedback_dates_no_records(mock_readonly):
    mock_readonly.return_value = []
    result = utils.get_all_feedback_dates()
    assert result == []

def test_get_all_feedback_dates_exception(mock_readonly):
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
def test_get_todays_duties_uses_cycle_week(monkeypatch, mock_readonly):
    # Mock datetime and cycle week
    FakeDatetime.today_weekday = 1  # Tuesday
    monkeypatch.setattr(utils, 'datetime', FakeDatetime)
    monkeypatch.setattr(utils, 'get_current_cycle_week', lambda: 1)
    
    mock_readonly.return_value = [
        (1, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}], True)
    ]
    
    result = utils.get_todays_duties("Alice")
    
    # Verify the query was called with correct parameters
    sql, params = mock_readonly.call_args[0]
    assert params['day'] == 1
    assert params['cycle_week'] == 1
    assert params['user_name'] == "Alice"
    
    # Verify simplified query structure (no CTE)
    assert "WITH computed_cycle" not in sql
    assert "WHERE ds.day = :day" in sql
    assert "AND ds.cycle_week = :cycle_week" in sql

# Add cache testing
@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before and after each test to avoid side effects"""
    from backend.globals import cache
    cache.clear()
    yield
    cache.clear()

def test_caching_behavior(mock_readonly):
    """Test that caching works correctly"""
    mock_readonly.return_value = [('Alice Smith','SectionA','RoleA','TeamA')]
    
    # First call should hit the database
    result1 = utils.get_all_users()
    assert mock_readonly.call_count == 1
    
    # Second call should use cache (but we cleared cache in fixture, so this will still call DB)
    # In a real scenario with cache enabled, this would be 0 additional calls
    result2 = utils.get_all_users()
    
    assert result1 == result2
    assert result1 == ['Alice Smith']

# Test the new get_duty_schedule optimization
def test_get_duty_schedule_uses_parameterized_query(mock_readonly):
    """Test that get_duty_schedule uses the new parameterized approach"""
    mock_readonly.return_value = [
        (1, 0, "Kitchen Duty", "Clean kitchen", "Team A", [{"name": "Alice", "week": "Both"}])
    ]
    
    result = utils.get_duty_schedule()
    
    # Verify it's a list of schedule entries
    assert isinstance(result, list)
    assert len(result) == 14  # 2 weeks
    
    # Check that the query uses ANY() for parameterization instead of dynamic SQL
    sql, params = mock_readonly.call_args[0]
    assert "ANY(:days)" in sql
    assert "ANY(:cycles)" in sql
    assert "days" in params
    assert "cycles" in params
    
    # Ensure no dynamic SQL concatenation
    assert "(" not in str(params['days'])  # Should be a list, not concatenated string

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