import pytest
from utils import get_all_users, get_user_duty, get_users_by_section, get_all_feedback_dates
from datetime import datetime

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