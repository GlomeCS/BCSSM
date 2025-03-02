from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from utils import (execute_query, get_all_feedback_dates, get_all_users, get_user_duty,
                   get_users_by_section, get_all_sections)


@pytest.fixture(autouse=True)
def mock_db_calls(mocker):
    # Automatically mock execute_query for all tests
    mock_execute_query = mocker.patch('utils.execute_query')
    return mock_execute_query


def test_get_all_users(mock_db_calls):
    # Mock database response
    mock_db_calls.return_value = [
        ('Alice', 'Minis', 'Section Leader', None),
        ('Bob', 'Micros', 'Team Member', 'Duty Team 1'),
        ('Charlie', 'Majors', 'Team Member', 'Duty Team 2')
    ]

    # Call the function
    result = get_all_users()

    # Assert results
    assert result == ['Alice', 'Bob', 'Charlie']

    # Match the exact SQL query format
    mock_db_calls.assert_called_once_with(
        """
    SELECT 
        u.name, 
        COALESCE(s.name, 'Unassigned') AS section,  -- Use 'Unassigned' if section is NULL
        u.role, 
        COALESCE(dt.name, 'No Team') AS team       -- Use 'No Team' if team is NULL
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id;
    """
    )


def test_get_user_duty_valid_user(mock_db_calls):
    today_index = datetime.now().weekday()
    duties = ["Breakfast", "Toilets", "Lunch", "General Clean", "Dinner", "Supper"]
    expected_duty = duties[today_index % len(duties)]

    # Mock database response
    mock_db_calls.return_value = [
        ('Ivy', 'Minis', 'Team Member', 'Duty Team 1', expected_duty)
    ]

    # Call the function
    result = get_user_duty("Ivy")

    # Assert results
    assert result == {
        "user": "Ivy",
        "section": "Minis",
        "role": "Team Member",  # Include role in the expected result
        "team": "Duty Team 1",
        "duty": expected_duty
    }
    mock_db_calls.assert_called_once()


def test_get_user_duty_invalid_user(mock_db_calls):
    # Simulate no user found
    mock_db_calls.return_value = []

    # Call the function
    result = get_user_duty("Unknown")

    # Assert results
    assert result == {"error": "User not found or no duty assigned"}
    mock_db_calls.assert_called_once()


def test_get_users_by_section(mock_db_calls):
    # Mock database response for section "Minis"
    mock_db_calls.return_value = [
        ('Alice', 'Section Leader'),
        ('Ivy', 'Team Member')
    ]

    # Call the function
    result = get_users_by_section("Minis")

    # Assert results
    assert result == [
        {"name": "Alice", "role": "Section Leader"},
        {"name": "Ivy", "role": "Team Member"}
    ]
    mock_db_calls.assert_called_once()


def test_get_all_feedback_dates_with_records(mock_db_calls):
    # Mock database response
    mock_db_calls.return_value = [
        ("2024-12-20",),
        ("2024-12-19",),
        ("2024-12-18",)
    ]

    # Call the function
    result = get_all_feedback_dates()

    # Assert results
    assert result == ["2024-12-20", "2024-12-19", "2024-12-18"]
    mock_db_calls.assert_called_once()


def test_get_all_feedback_dates_no_records(mock_db_calls):
    # Mock database response
    mock_db_calls.return_value = []

    # Call the function
    result = get_all_feedback_dates()

    # Assert results
    assert result == []
    mock_db_calls.assert_called_once()



@pytest.fixture
def mock_db_session():
    """Fixture to mock db.session"""
    with patch("utils.db.session") as mock_session:
        yield mock_session


def test_execute_query_success_with_results(mock_db_session):
    """Test execute_query when query returns rows"""
    mock_result = MagicMock()
    mock_result.returns_rows = True
    mock_result.fetchall.return_value = [("Alice",), ("Bob",)]
    
    mock_db_session.execute.return_value = mock_result

    query = "SELECT name FROM users"
    result = execute_query(query)

    mock_db_session.begin.assert_called_once()
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()
    assert result == [("Alice",), ("Bob",)]


def test_execute_query_success_no_results(mock_db_session):
    """Test execute_query when query does not return rows"""
    mock_result = MagicMock()
    mock_result.returns_rows = False

    mock_db_session.execute.return_value = mock_result

    query = "UPDATE users SET name='John' WHERE id=1"
    result = execute_query(query)

    mock_db_session.begin.assert_called_once()
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()
    assert result is None


def test_execute_query_failure(mock_db_session):
    """Test execute_query when an exception occurs"""
    mock_db_session.execute.side_effect = Exception("DB error")

    query = "DELETE FROM users WHERE id=1"

    with pytest.raises(Exception, match="DB error"):
        execute_query(query)

    mock_db_session.begin.assert_called_once()
    mock_db_session.rollback.assert_called_once()
    mock_db_session.commit.assert_not_called()

def test_get_users_by_section_exception(mocker):
    """Test get_users_by_section handles exceptions correctly"""
    
    # Mock execute_query to raise an exception
    mock_execute_query = mocker.patch("utils.execute_query")
    mock_execute_query.side_effect = Exception("Database error")

    section_name = "Minors"

    result = get_users_by_section(section_name)

    # Ensure it returns the expected error message
    assert "error" in result
    assert "Failed to fetch users by section" in result["error"]
    assert "Database error" in result["error"]

    # Verify the mocked function was called with the correct parameters
    expected_query = """
    SELECT u.name, u.role
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    WHERE s.name = :section;
    """.strip()  # Strip whitespace to match actual call

    actual_query, actual_params = mock_execute_query.call_args[0]  # Get actual call args

    assert actual_query.strip() == expected_query  # Ensure query matches ignoring whitespace
    assert actual_params == {"section": section_name}  # Ensure params match

def test_get_all_sections_with_records(mock_db_calls):
    """Test get_all_sections when sections exist"""
    # Mock database response with some section names
    mock_db_calls.return_value = [("Minis",), ("Micros",), ("Majors",)]

    # Call the function
    result = get_all_sections()

    # Assert results
    assert result == ["Minis", "Micros", "Majors"]
    mock_db_calls.assert_called_once_with(
        """
    SELECT name
    FROM sections
    ORDER BY name;
    """
    )


def test_get_all_sections_no_records(mock_db_calls):
    """Test get_all_sections when no sections exist"""
    # Mock database returning an empty list
    mock_db_calls.return_value = []

    # Call the function
    result = get_all_sections()

    # Assert results
    assert result == []
    mock_db_calls.assert_called_once()


def test_get_all_sections_exception(mocker):
    """Test get_all_sections handles exceptions correctly"""
    
    # Mock execute_query to raise an exception
    mock_execute_query = mocker.patch("utils.execute_query")
    mock_execute_query.side_effect = Exception("Database error")

    result = get_all_sections()

    # Ensure it returns the expected error message
    assert "error" in result
    assert "Failed to fetch sections" in result["error"]
    assert "Database error" in result["error"]

    # Verify the query was called
    expected_query = """
    SELECT name
    FROM sections
    ORDER BY name;
    """.strip()

    actual_query = mock_execute_query.call_args[0][0]  # Get actual query argument

    assert actual_query.strip() == expected_query  # Ensure query matches ignoring whitespace

def test_get_all_feedback_dates_exception(mocker):
    """Test get_all_feedback_dates handles exceptions correctly"""
    
    # Mock execute_query to raise an exception
    mock_execute_query = mocker.patch("utils.execute_query")
    mock_execute_query.side_effect = Exception("Database error")

    result = get_all_feedback_dates()

    # Ensure it returns the expected error message
    assert "error" in result
    assert "Failed to fetch feedback dates" in result["error"]
    assert "Database error" in result["error"]

    # Verify the query was called
    expected_query = """
    SELECT DISTINCT date
    FROM feedback_records
    ORDER BY date DESC;
    """.strip()

    actual_query = mock_execute_query.call_args[0][0]  # Get actual query argument

    assert actual_query.strip() == expected_query  # Ensure query matches ignoring whitespace

def test_get_user_duty_exception(mocker):
    """Test get_user_duty handles exceptions correctly"""
    
    # Mock execute_query to raise an exception
    mock_execute_query = mocker.patch("utils.execute_query")
    mock_execute_query.side_effect = Exception("Database error")

    user_name = "JohnDoe"

    result = get_user_duty(user_name)

    # Ensure it returns the expected error message
    assert "error" in result
    assert "Failed to fetch duty for user" in result["error"]
    assert "Database error" in result["error"]

    # Verify the query was called with expected parameters
    expected_query = """
    SELECT 
        u.name AS user_name, 
        COALESCE(s.name, 'Unassigned') AS section, 
        u.role, 
        COALESCE(dt.name, 'No Team') AS team,
        COALESCE(d.name, 'No Duty') AS duty
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id
    LEFT JOIN duty_schedule ds ON dt.id = ds.duty_team_id AND ds.day = :day
    LEFT JOIN duties d ON ds.duty_id = d.id
    WHERE u.name = :user_name;
    """.strip()

    actual_query, actual_params = mock_execute_query.call_args[0]  # Extract actual call arguments

    assert actual_query.strip() == expected_query  # Strip to avoid whitespace mismatches
    assert actual_params["user_name"] == user_name  # Ensure user_name matches
    assert isinstance(actual_params["day"], int)  # Ensure "day" parameter is an integer