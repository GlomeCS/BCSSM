# backend/tests/test_duties_routes.py
# Unit tests for duties routes — session-only auth model

import pytest
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend import create_app
from unittest.mock import MagicMock
import logging

# ─── 0) Fixture: create app with testing config ────────────────────────────────
@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app()
    return app

# ─── 1) Fixture: test client ───────────────────────────────────────────────────
@pytest.fixture
def client(app):
    return app.test_client()

# ─── 2) Patch utility functions used by duties routes ─────────────────────────
@pytest.fixture(autouse=True)
def patch_duties_helpers(monkeypatch):
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

# ─── 3) Tests for GET /api/duties/today ───────────────────────────────────────
def test_get_duties_today_success_with_session(client, patch_duties_helpers):
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

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/today")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == mock_duties
    ph["todays_duties"].assert_called_once_with("Alice")


def test_get_duties_today_query_param_rejected(client, patch_duties_helpers):
    """Query param user_name is not trusted — session required."""
    resp = client.get("/api/duties/today?user_name=Alice")
    assert resp.status_code == 401
    patch_duties_helpers["todays_duties"].assert_not_called()


def test_get_duties_today_header_rejected(client, patch_duties_helpers):
    """X-Current-User header is not trusted — session required."""
    resp = client.get("/api/duties/today", headers={"X-Current-User": "Bob"})
    assert resp.status_code == 401
    patch_duties_helpers["todays_duties"].assert_not_called()


def test_get_duties_today_no_username(client, patch_duties_helpers):
    """No session → 401."""
    resp = client.get("/api/duties/today")
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]
    patch_duties_helpers["todays_duties"].assert_not_called()


def test_get_duties_today_session_takes_priority_over_other_sources(client, patch_duties_helpers):
    """Session is the only trusted source; other sources are ignored."""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    with client.session_transaction() as sess:
        sess["user_name"] = "SessionUser"

    # Query param and header are both present but must be ignored
    resp = client.get("/api/duties/today?user_name=QueryUser",
                      headers={"X-Current-User": "HeaderUser"})
    assert resp.status_code == 200
    ph["todays_duties"].assert_called_once_with("SessionUser")


def test_get_duties_today_exception_handling(client, patch_duties_helpers):
    ph = patch_duties_helpers
    ph["todays_duties"].side_effect = SQLAlchemyError("Database connection failed")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/today")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "Failed to fetch today's duties" in data["error"]


def test_get_duties_today_unexpected_exception(client, patch_duties_helpers):
    ph = patch_duties_helpers
    ph["todays_duties"].side_effect = IndexError("row index out of range")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/today")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "Failed to fetch today's duties" in data["error"]


def test_get_duties_today_empty_result(client, patch_duties_helpers):
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/today")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_duties_today_complex_duties_data(client, patch_duties_helpers):
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

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/today")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["name"] == "Kitchen Duty"
    assert data[0]["is_current_user"] is True
    assert len(data[0]["members"]) == 3
    assert data[1]["name"] == "Security Duty"
    assert data[1]["is_current_user"] is False


# ─── 4) Tests for GET /api/duties/schedule ────────────────────────────────────
def test_get_duty_schedule_success_with_session(client, patch_duties_helpers):
    ph = patch_duties_helpers
    mock_schedule = [
        {
            "date": "2026-07-04",
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

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "schedule" in data
    assert data["schedule"] == mock_schedule
    ph["duty_schedule"].assert_called_once()


def test_get_duty_schedule_query_param_rejected(client, patch_duties_helpers):
    """Query param is not trusted for auth — session required."""
    resp = client.get("/api/duties/schedule?user_name=Alice")
    assert resp.status_code == 401
    patch_duties_helpers["duty_schedule"].assert_not_called()


def test_get_duty_schedule_header_rejected(client, patch_duties_helpers):
    """Header is not trusted for auth — session required."""
    resp = client.get("/api/duties/schedule", headers={"X-Current-User": "Bob"})
    assert resp.status_code == 401
    patch_duties_helpers["duty_schedule"].assert_not_called()


def test_get_duty_schedule_no_username(client, patch_duties_helpers):
    """No session → 401."""
    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]
    patch_duties_helpers["duty_schedule"].assert_not_called()


def test_get_duty_schedule_exception_handling(client, patch_duties_helpers):
    ph = patch_duties_helpers
    ph["duty_schedule"].side_effect = SQLAlchemyError("Schedule service unavailable")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "Failed to fetch duty schedule" in data["error"]


def test_get_duty_schedule_unexpected_exception(client, patch_duties_helpers):
    ph = patch_duties_helpers
    ph["duty_schedule"].side_effect = ValueError("unexpected data format")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "Failed to fetch duty schedule" in data["error"]


def test_get_duty_schedule_complex_schedule_data(client, patch_duties_helpers):
    ph = patch_duties_helpers
    mock_schedule = [
        {
            "date": "2026-07-04",
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
            "date": "2026-07-05",
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

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["schedule"]) == 2
    assert data["schedule"][0]["date"] == "2026-07-04"
    assert len(data["schedule"][0]["duties"]) == 2
    assert data["schedule"][1]["date"] == "2026-07-05"
    assert len(data["schedule"][1]["duties"]) == 1


def test_get_duty_schedule_two_week_period(client, patch_duties_helpers):
    ph = patch_duties_helpers
    mock_schedule = []
    for i in range(14):
        day_data = {
            "date": f"2026-07-{4+i:02d}",
            "day_name": "Saturday",
            "week": "Week A" if i < 7 else "Week B",
            "duties": []
        }
        mock_schedule.append(day_data)

    ph["duty_schedule"].return_value = mock_schedule

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/duties/schedule")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["schedule"]) == 14
    assert data["schedule"][0]["date"] == "2026-07-04"
    assert data["schedule"][13]["date"] == "2026-07-17"


# ─── 5) Tests for username handling edge cases ─────────────────────────────────
def test_username_with_spaces_via_session(client, patch_duties_helpers):
    """Usernames with spaces are supported when stored in session."""
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = []

    with client.session_transaction() as sess:
        sess["user_name"] = "John Doe"

    resp = client.get("/api/duties/today")
    assert resp.status_code == 200
    ph["todays_duties"].assert_called_once_with("John Doe")


def test_empty_username_in_query_param(client, patch_duties_helpers):
    """Empty query param → still no session → 401."""
    resp = client.get("/api/duties/today?user_name=")
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]


# ─── 6) Tests for logging behavior ────────────────────────────────────────────
def test_logging_on_successful_request(client, patch_duties_helpers, caplog):
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = [{"id": "123", "name": "Test"}]

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    with caplog.at_level(logging.INFO):
        resp = client.get("/api/duties/today")

    assert resp.status_code == 200
    assert "Retrieved 1 duties for user Alice" in caplog.text


def test_logging_on_missing_username(client, patch_duties_helpers, caplog):
    """No session → 401; no route-level log since decorator handles it."""
    resp = client.get("/api/duties/today")
    assert resp.status_code == 401


def test_logging_on_exception(client, patch_duties_helpers, caplog):
    ph = patch_duties_helpers
    ph["todays_duties"].side_effect = SQLAlchemyError("Test error")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    with caplog.at_level(logging.ERROR):
        resp = client.get("/api/duties/today")

    assert resp.status_code == 500
    assert "Error fetching today's duties for user Alice" in caplog.text
    assert "Test error" in caplog.text


# ─── 7) Integration tests for both endpoints together ─────────────────────────
def test_both_endpoints_with_same_user(client, patch_duties_helpers):
    ph = patch_duties_helpers
    ph["todays_duties"].return_value = [{"id": "123", "name": "Today's duty"}]
    ph["duty_schedule"].return_value = [{"date": "2026-07-04", "duties": []}]

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp1 = client.get("/api/duties/today")
    assert resp1.status_code == 200
    assert resp1.get_json()[0]["name"] == "Today's duty"

    resp2 = client.get("/api/duties/schedule")
    assert resp2.status_code == 200
    assert resp2.get_json()["schedule"][0]["date"] == "2026-07-04"

    ph["todays_duties"].assert_called_once_with("Alice")
    ph["duty_schedule"].assert_called_once()


def test_both_endpoints_require_session(client, patch_duties_helpers):
    """Without a session, both endpoints return 401."""
    resp1 = client.get("/api/duties/today")
    assert resp1.status_code == 401

    resp2 = client.get("/api/duties/schedule")
    assert resp2.status_code == 401
