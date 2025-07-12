# backend/tests/test_duties_routes.py
# Comprehensive unit tests for duties routes with persistent authentication

import pytest
from backend.bcssm_backend import create_app
from unittest.mock import MagicMock, patch
import logging

# ─── 0) Fixture: create app with testing config and register routes ────────────
@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app()
    return app

# ─── 1) Fixture: test client ─────────────────────────────────────────────────────
@pytest.fixture
def client(app):
    return app.test_client()

# ─── 2) Patch utility functions used by duties routes ──────────────────────────
@pytest.fixture(autouse=True)
def patch_duties_helpers(monkeypatch):
    """Patch the utility functions used by duties routes"""
    fake_get_todays_duties = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.duties.get_todays_duties",
        fake_get_todays_duties
    )
    
    fake_get_duty_schedule = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.duties.get_duty_schedule",
        fake_get_duty_schedule
    )
    
    return {
        "todays_duties": fake_get_todays_duties,
        "duty_schedule": fake_get_duty_schedule
    }

# ─── 3) Tests for GET /api/duties/today ─────────────────────────────────────────
def test_get_duties_today_success_with_query_param(client, patch_duties_helpers):
    """Test /api/duties/today with username via query parameter"""
    ph = patch_duties_helpers
    mock_duties = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Kitchen Duty",
            "duty_description": "Clean kitchen and dining area",
            "team_name": "Team Alpha",
            "members": [{"name": "Alice", "week": "Both"}],
            "is_current_user": True
        }
    ]
    ph["todays_duties"].return_value = mock_duties

    resp = client.get("/api/duties/today?user_name=Alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == mock_duties
    
    # Verify the utility function was called correctly
    ph["todays_duties"].assert_called_once_with("Alice")

def test_get_duties_today_success_with_header(client, patch_duties_helpers):
    """Test /api/duties/today with username via X-Current-User header"""
    ph = patch_duties_helpers
    mock_duties = [
        {
            "id": "456e7890-e89b-12d3-a456-426614174001",
            "name": "Security Duty",
            "duty_description": "Monitor entrance and exits",
            "team_name": "Team Beta",
            "members": [{"name": "Bob", "week": "Week A"}],
            "is_current_user": False
        }
    ]
    ph["todays_duties"].return_value = mock_duties

    resp = client.get("/api/duties/today", headers={"X-Current-User": "Bob"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == mock_duties
    ph["todays_duties"].assert_called_once_with("Bob")

def test_get_duties_today_success_with_session(client, patch_duties_helpers):
    """Test /api/duties/today with username via session (backward compatibility)"""
    ph = patch_duties_helpers
    mock_duties = []  # No duties for this user
    ph["todays_duties"].return_value = mock_duties

    with client.session_transaction() as sess:
        sess["user_name"] = "Charlie"

    resp = client.get("/api/duties/today")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == []
    ph["todays_duties"].assert_called_once_with("Charlie")

def test_get_duties_today_no_username(client, patch_duties_helpers):
    """Test /api/duties/today without any username source"""
    resp = client.get("/api/duties/today")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Username required" in data["error"]
    
    # Verify utility function was not called
    ph = patch_duties_helpers
    ph["todays_duties"].assert_not_called()

def test_get_duties_today_multiple_auth_sources_priority(client, patch_duties_helpers):
    """Test that query parameter takes priority over other auth sources"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    # Set up multiple potential username sources
    with client.session_transaction() as sess:
        sess["user_name"] = "SessionUser"

    # Query param should take priority
    resp = client.get("/api/duties/today?user_name=QueryUser", 
                     headers={"X-Current-User": "HeaderUser"})
    assert resp.status_code == 200
    
    # Should use query param username
    ph["todays_duties"].assert_called_once_with("QueryUser")

def test_get_duties_today_url_encoded_username(client, patch_duties_helpers):
    """Test /api/duties/today with URL-encoded username"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    # Test with spaces in username (URL encoded as %20)
    resp = client.get("/api/duties/today?user_name=John%20Doe")
    assert resp.status_code == 200
    
    # Should decode the username properly
    ph["todays_duties"].assert_called_once_with("John Doe")

def test_get_duties_today_exception_handling(client, patch_duties_helpers):
    """Test /api/duties/today when get_todays_duties raises exception"""
    ph = patch_duties_helpers
    ph["todays_duties"].side_effect = Exception("Database connection failed")

    resp = client.get("/api/duties/today?user_name=Alice")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "Failed to fetch today's duties" in data["error"]

def test_get_duties_today_empty_result(client, patch_duties_helpers):
    """Test /api/duties/today when user has no duties"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    resp = client.get("/api/duties/today?user_name=Alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == []

def test_get_duties_today_complex_duties_data(client, patch_duties_helpers):
    """Test /api/duties/today with complex duties data structure"""
    ph = patch_duties_helpers
    mock_duties = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Kitchen Duty",
            "duty_description": "Clean kitchen and dining area thoroughly",
            "team_name": "Team Alpha",
            "members": [
                {"name": "Alice", "week": "Both"},
                {"name": "Bob", "week": "Week A"},
                {"name": "Charlie", "week": "Week B"}
            ],
            "is_current_user": True
        },
        {
            "id": "456e7890-e89b-12d3-a456-426614174001",
            "name": "Security Duty",
            "duty_description": "Monitor all entrance and exit points",
            "team_name": "Team Beta",
            "members": [
                {"name": "David", "week": "Both"},
                {"name": "Eve", "week": "Week A"}
            ],
            "is_current_user": False
        }
    ]
    ph["todays_duties"].return_value = mock_duties

    resp = client.get("/api/duties/today?user_name=Alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["name"] == "Kitchen Duty"
    assert data[0]["is_current_user"] is True
    assert len(data[0]["members"]) == 3
    assert data[1]["name"] == "Security Duty"
    assert data[1]["is_current_user"] is False

# ─── 4) Tests for GET /api/duties/schedule ──────────────────────────────────────
def test_get_duty_schedule_success_with_query_param(client, patch_duties_helpers):
    """Test /api/duties/schedule with username via query parameter"""
    ph = patch_duties_helpers
    mock_schedule = [
        {
            "date": "2025-07-05",
            "day_name": "Saturday",
            "week": "Week A",
            "duties": [
                {
                    "duty_name": "Security",
                    "duty_description": "Monitor entrance",
                    "team_name": "Team Alpha",
                    "team_members": [{"name": "Alice", "week": "Both"}]
                }
            ]
        }
    ]
    ph["duty_schedule"].return_value = mock_schedule

    resp = client.get("/api/duties/schedule?user_name=Alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "schedule" in data
    assert data["schedule"] == mock_schedule
    
    # Verify the utility function was called
    ph["duty_schedule"].assert_called_once()

def test_get_duty_schedule_success_with_header(client, patch_duties_helpers):
    """Test /api/duties/schedule with username via header"""
    ph = patch_duties_helpers
    mock_schedule = []  # Empty schedule
    ph["duty_schedule"].return_value = mock_schedule

    resp = client.get("/api/duties/schedule", headers={"X-Current-User": "Bob"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["schedule"] == []
    ph["duty_schedule"].assert_called_once()

def test_get_duty_schedule_success_with_session(client, patch_duties_helpers):
    """Test /api/duties/schedule with username via session"""
    ph = patch_duties_helpers
    mock_schedule = [
        {
            "date": "2025-07-06",
            "day_name": "Sunday",
            "week": "Week A",
            "duties": []
        }
    ]
    ph["duty_schedule"].return_value = mock_schedule

    with client.session_transaction() as sess:
        sess["user_name"] = "Charlie"

    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["schedule"] == mock_schedule

def test_get_duty_schedule_no_username(client, patch_duties_helpers):
    """Test /api/duties/schedule without any username source"""
    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Username required" in data["error"]
    
    # Verify utility function was not called
    ph = patch_duties_helpers
    ph["duty_schedule"].assert_not_called()

def test_get_duty_schedule_exception_handling(client, patch_duties_helpers):
    """Test /api/duties/schedule when get_duty_schedule raises exception"""
    ph = patch_duties_helpers
    ph["duty_schedule"].side_effect = Exception("Schedule service unavailable")

    resp = client.get("/api/duties/schedule?user_name=Alice")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "Failed to fetch duty schedule" in data["error"]

def test_get_duty_schedule_complex_schedule_data(client, patch_duties_helpers):
    """Test /api/duties/schedule with complex schedule data"""
    ph = patch_duties_helpers
    mock_schedule = [
        {
            "date": "2025-07-05",
            "day_name": "Saturday",
            "week": "Week A",
            "duties": [
                {
                    "duty_name": "Kitchen Duty",
                    "duty_description": "Clean kitchen and dining area",
                    "team_name": "Team Alpha",
                    "team_members": [
                        {"name": "Alice", "week": "Both"},
                        {"name": "Bob", "week": "Week A"}
                    ]
                },
                {
                    "duty_name": "Security Duty",
                    "duty_description": "Monitor entrance and exits",
                    "team_name": "Team Beta",
                    "team_members": [
                        {"name": "Charlie", "week": "Week A"},
                        {"name": "David", "week": "Both"}
                    ]
                }
            ]
        },
        {
            "date": "2025-07-06",
            "day_name": "Sunday",
            "week": "Week A",
            "duties": [
                {
                    "duty_name": "Cleaning Duty",
                    "duty_description": "General cleaning",
                    "team_name": "Team Gamma",
                    "team_members": [{"name": "Eve", "week": "Both"}]
                }
            ]
        }
    ]
    ph["duty_schedule"].return_value = mock_schedule

    resp = client.get("/api/duties/schedule?user_name=Alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["schedule"]) == 2
    assert data["schedule"][0]["date"] == "2025-07-05"
    assert len(data["schedule"][0]["duties"]) == 2
    assert data["schedule"][1]["date"] == "2025-07-06"
    assert len(data["schedule"][1]["duties"]) == 1

def test_get_duty_schedule_two_week_period(client, patch_duties_helpers):
    """Test /api/duties/schedule returns 2-week period as documented"""
    ph = patch_duties_helpers
    # Mock 14 days of schedule data
    mock_schedule = []
    for i in range(14):
        day_data = {
            "date": f"2025-07-{5+i:02d}",
            "day_name": "Saturday",  # Simplified for test
            "week": "Week A" if i < 7 else "Week B",
            "duties": []
        }
        mock_schedule.append(day_data)
    
    ph["duty_schedule"].return_value = mock_schedule

    resp = client.get("/api/duties/schedule?user_name=Alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["schedule"]) == 14
    assert data["schedule"][0]["date"] == "2025-07-05"
    assert data["schedule"][13]["date"] == "2025-07-18"

# ─── 5) Tests for authentication method priority ────────────────────────────────
def test_auth_priority_query_over_header(client, patch_duties_helpers):
    """Test that query parameter takes priority over header"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    resp = client.get("/api/duties/today?user_name=QueryUser", 
                     headers={"X-Current-User": "HeaderUser"})
    assert resp.status_code == 200
    ph["todays_duties"].assert_called_once_with("QueryUser")

def test_auth_priority_query_over_session(client, patch_duties_helpers):
    """Test that query parameter takes priority over session"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    with client.session_transaction() as sess:
        sess["user_name"] = "SessionUser"

    resp = client.get("/api/duties/today?user_name=QueryUser")
    assert resp.status_code == 200
    ph["todays_duties"].assert_called_once_with("QueryUser")

def test_auth_priority_header_over_session(client, patch_duties_helpers):
    """Test that header takes priority over session"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    with client.session_transaction() as sess:
        sess["user_name"] = "SessionUser"

    resp = client.get("/api/duties/today", headers={"X-Current-User": "HeaderUser"})
    assert resp.status_code == 200
    ph["todays_duties"].assert_called_once_with("HeaderUser")

# ─── 6) Tests for username handling edge cases ──────────────────────────────────
def test_username_with_special_characters(client, patch_duties_helpers):
    """Test usernames with special characters are handled correctly"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    # Test with apostrophe in name
    resp = client.get("/api/duties/today?user_name=O'Connor")
    assert resp.status_code == 200
    # The escape() function converts apostrophe to HTML entity
    from markupsafe import Markup
    ph["todays_duties"].assert_called_once_with(Markup("O&#39;Connor"))

def test_username_with_spaces_via_header(client, patch_duties_helpers):
    """Test usernames with spaces via header"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    resp = client.get("/api/duties/today", headers={"X-Current-User": "John Doe"})
    assert resp.status_code == 200
    ph["todays_duties"].assert_called_once_with("John Doe")

def test_empty_username_in_query_param(client, patch_duties_helpers):
    """Test empty username in query parameter"""
    resp = client.get("/api/duties/today?user_name=")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Username required" in data["error"]

def test_empty_username_in_header(client, patch_duties_helpers):
    """Test empty username in header"""
    resp = client.get("/api/duties/today", headers={"X-Current-User": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Username required" in data["error"]

# ─── 7) Tests for logging behavior ──────────────────────────────────────────────
def test_logging_on_successful_request(client, patch_duties_helpers, caplog):
    """Test that successful requests are logged appropriately"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = [{"id": "123", "name": "Test"}]

    with caplog.at_level(logging.INFO):
        resp = client.get("/api/duties/today?user_name=Alice")
    
    assert resp.status_code == 200
    assert "Retrieved 1 duties for user Alice" in caplog.text

def test_logging_on_missing_username(client, patch_duties_helpers, caplog):
    """Test that missing username warnings are logged"""
    with caplog.at_level(logging.WARNING):
        resp = client.get("/api/duties/today")
    
    assert resp.status_code == 400
    assert "No username found in request for /api/duties/today" in caplog.text

def test_logging_on_exception(client, patch_duties_helpers, caplog):
    """Test that exceptions are logged with proper context"""
    ph = patch_duties_helpers
    ph["todays_duties"].side_effect = Exception("Test error")

    with caplog.at_level(logging.ERROR):
        resp = client.get("/api/duties/today?user_name=Alice")
    
    assert resp.status_code == 500
    assert "Error fetching today's duties for user Alice" in caplog.text
    assert "Test error" in caplog.text

# ─── 8) Integration tests for both endpoints together ───────────────────────────
def test_both_endpoints_with_same_user(client, patch_duties_helpers):
    """Test that both endpoints work correctly with the same user"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = [{"id": "123", "name": "Today's duty"}]
    ph["duty_schedule"].return_value = [{"date": "2025-07-05", "duties": []}]

    # Test today's duties
    resp1 = client.get("/api/duties/today?user_name=Alice")
    assert resp1.status_code == 200
    assert resp1.get_json()[0]["name"] == "Today's duty"

    # Test schedule
    resp2 = client.get("/api/duties/schedule?user_name=Alice")
    assert resp2.status_code == 200
    assert resp2.get_json()["schedule"][0]["date"] == "2025-07-05"

    # Verify both utility functions were called
    ph["todays_duties"].assert_called_once_with("Alice")
    ph["duty_schedule"].assert_called_once()

def test_endpoints_with_different_auth_methods(client, patch_duties_helpers):
    """Test endpoints using different authentication methods"""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []
    ph["duty_schedule"].return_value = []

    # Today's duties via query param
    resp1 = client.get("/api/duties/today?user_name=Alice")
    assert resp1.status_code == 200

    # Schedule via header
    resp2 = client.get("/api/duties/schedule", headers={"X-Current-User": "Bob"})
    assert resp2.status_code == 200

    # Verify correct usernames were used
    ph["todays_duties"].assert_called_once_with("Alice")
    ph["duty_schedule"].assert_called_once()  # get_duty_schedule doesn't take username param