import pytest
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend import create_app
from backend.bcssm_backend.routes.devos_feedback import (
    get_feedback_by_date,
    get_user_info,
)
from urllib.parse import quote
from unittest.mock import MagicMock

# ─── 0) Fixture: use TestingConfig and register routes ──────────────────────────
@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app()
    # routes for devos_feedback are already registered by create_app()
    # init_feedback_routes(app)
    return app

# ─── 1) Fixture: test client ─────────────────────────────────────────────────────
@pytest.fixture
def client(app):
    return app.test_client()

# ─── 2) Patch execute_query in devos_feedback ───────────────────────────────────
@pytest.fixture(autouse=True)
def mock_execute_query(monkeypatch):
    mock_exec = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.devos_feedback.execute_query",
        mock_exec
    )
    return mock_exec

# ─── 3) Unit tests for get_feedback_by_date ──────────────────────────────────────
def test_get_feedback_by_date_success(mock_execute_query):
    mock_execute_query.return_value = [("Minis", "Great job"), ("Majors", None)]
    result, error = get_feedback_by_date("2025-06-07")
    assert error is None
    assert result == {
        "Minis": "Great job",
        "Majors": "No feedback available"
    }

def test_get_feedback_by_date_exception(mock_execute_query):
    mock_execute_query.side_effect = SQLAlchemyError("DB fail")
    result, error = get_feedback_by_date("2025-06-07")
    assert result is None
    assert error == "An error occurred while fetching feedback"

# ─── 4) Unit tests for get_user_info ────────────────────────────────────────────
def test_get_user_info_found(mock_execute_query):
    mock_execute_query.return_value = [("Alice", "Leader", "Minis")]
    info = get_user_info("Alice")
    assert info == {"name": "Alice", "role": "Leader", "section": "Minis"}

def test_get_user_info_not_found(mock_execute_query):
    mock_execute_query.return_value = []
    info = get_user_info("Bob")
    assert info is None

def test_get_user_info_exception(mock_execute_query):
    mock_execute_query.side_effect = SQLAlchemyError("Oops")
    with pytest.raises(SQLAlchemyError):
        get_user_info("Alice")

# ─── 5) Integration tests for GET /api/devos-feedback ───────────────────────────
@pytest.fixture(autouse=True)
def patch_helpers(monkeypatch):
    fake_fb = MagicMock(return_value=({}, None))
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.devos_feedback.get_feedback_by_date",
        fake_fb
    )
    fake_ui = MagicMock(return_value=None)
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.devos_feedback.get_user_info",
        fake_ui
    )
    return fake_fb, fake_ui

def test_route_default_date_no_user(client, patch_helpers):
    """Test route without any username - should return 400"""
    fake_fb, fake_ui = patch_helpers
    resp = client.get("/api/devos-feedback")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Username required" in data["error"]

def test_route_default_date_with_user(client, patch_helpers):
    """Test route with username via query parameter"""
    fake_fb, fake_ui = patch_helpers
    # Mock get_user_info to return valid user data
    fake_ui.return_value = {"name": "TestUser", "role": "Team Member", "section": "TestSection"}
    
    resp = client.get("/api/devos-feedback?user_name=TestUser")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "date" in data
    assert data["feedback"] == {}
    assert data["user"]["name"] == "TestUser"
    assert data["is_leader"] is False

def test_route_with_date_and_leader_via_header(client, patch_helpers):
    """Test route with username via header"""
    fake_fb, fake_ui = patch_helpers
    fake_fb.return_value = ({"X": "Y"}, None)
    fake_ui.return_value = {"name": "A", "role": "Section Leader", "section": "S"}

    date_str = "2025-06-07"
    resp = client.get(f"/api/devos-feedback?date={quote(date_str)}", 
                     headers={"X-Current-User": "A"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["date"] == date_str
    assert data["feedback"] == {"X": "Y"}
    assert data["user"] == {"name": "A", "role": "Section Leader", "section": "S"}
    assert data["is_leader"] is True

def test_route_with_date_and_leader_via_session(client, patch_helpers):
    """Test route with username via session (backward compatibility)"""
    fake_fb, fake_ui = patch_helpers
    fake_fb.return_value = ({"X": "Y"}, None)
    fake_ui.return_value = {"name": "A", "role": "Section Leader", "section": "S"}

    with client.session_transaction() as sess:
        sess["user_name"] = "A"

    date_str = "2025-06-07"
    resp = client.get(f"/api/devos-feedback?date={quote(date_str)}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["date"] == date_str
    assert data["feedback"] == {"X": "Y"}
    assert data["user"] == {"name": "A", "role": "Section Leader", "section": "S"}
    assert data["is_leader"] is True

def test_route_invalid_user(client, patch_helpers):
    """Test route with username that doesn't exist"""
    fake_fb, fake_ui = patch_helpers
    # Mock get_user_info to return None (user not found)
    fake_ui.return_value = None
    
    resp = client.get("/api/devos-feedback?user_name=NonExistentUser")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Invalid user" in data["error"]

def test_route_feedback_error(client, patch_helpers):
    """Test route when feedback fetch fails"""
    fake_fb, fake_ui = patch_helpers
    fake_fb.return_value = (None, "err")
    fake_ui.return_value = {"name": "TestUser", "role": "Team Member", "section": "TestSection"}
    
    resp = client.get("/api/devos-feedback?date=2025-06-07&user_name=TestUser")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Internal server error"}

# ─── 6) Integration tests for POST /api/devos-feedback/edit ────────────────────
def test_edit_unauthenticated(client):
    """Test edit without any authentication - should return 400"""
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Username required" in data["error"]

def test_edit_authenticated_via_query_param(client, mock_execute_query):
    """Test edit with username via query parameter"""
    # Mock user lookup and section lookup
    calls = []
    def side_effect(query, params=None):
        calls.append((query, params))
        if "SELECT u.id FROM users u WHERE u.name" in query:
            return [(1,)]  # Return user ID
        elif "SELECT id FROM sections" in query:
            return [(5,)]  # Return section ID
        else:
            return None  # Upsert query
    
    mock_execute_query.side_effect = side_effect
    
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis&user_name=TestUser",
                       json={"feedback": "Test"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}

def test_edit_authenticated_via_header(client, mock_execute_query):
    """Test edit with username via header"""
    calls = []
    def side_effect(query, params=None):
        calls.append((query, params))
        if "SELECT u.id FROM users u WHERE u.name" in query:
            return [(1,)]  # Return user ID
        elif "SELECT id FROM sections" in query:
            return [(5,)]  # Return section ID
        else:
            return None  # Upsert query
    
    mock_execute_query.side_effect = side_effect
    
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"},
                       headers={"X-Current-User": "TestUser"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}

def test_edit_authenticated_via_session(client, mock_execute_query):
    """Test edit with session user_id (no username in request, falls back to session)"""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    calls = []
    def side_effect(query, params=None):
        calls.append((query, params))
        if "SELECT id FROM sections" in query:
            return [(5,)]  # Return section ID
        else:
            return None  # Upsert query

    mock_execute_query.side_effect = side_effect

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}

def test_edit_missing_params(client):
    """Test edit with missing parameters"""
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&user_name=TestUser",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    assert "Missing date, section, or feedback" in resp.get_json()["error"]

def test_edit_section_not_found(client, mock_execute_query):
    """Test edit when section doesn't exist"""
    # Mock user lookup to succeed, section lookup to fail
    def side_effect(query, params=None):
        if "SELECT u.id FROM users u WHERE u.name" in query:
            return [(1,)]  # Return user ID
        elif "SELECT id FROM sections" in query:
            return []  # Section not found
        else:
            return None
    
    mock_execute_query.side_effect = side_effect
    
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis&user_name=TestUser",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    assert "Section 'Minis' not found" in resp.get_json()["error"]

def test_edit_success(client, mock_execute_query):
    """Test successful edit operation"""
    calls = []
    def side_effect(query, params=None):
        calls.append((query, params))
        if "SELECT u.id FROM users u WHERE u.name" in query:
            return [(1,)]  # Return user ID
        elif "SELECT id FROM sections" in query:
            return [(5,)]  # Return section ID
        else:
            return None  # Upsert query
    
    mock_execute_query.side_effect = side_effect
    
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis&user_name=TestUser",
                       json={"feedback": "New"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}
    assert len(calls) == 3  # User lookup, section lookup, upsert
    assert any("SELECT u.id FROM users u WHERE u.name" in call[0] for call in calls)
    assert any("SELECT id FROM sections" in call[0] for call in calls)
    assert any("INSERT INTO feedback" in call[0] for call in calls)

def test_edit_upsert_error(client, mock_execute_query):
    """Test edit when upsert operation fails with SQLAlchemyError"""
    def side_effect(query, params=None):
        if "SELECT u.id FROM users u WHERE u.name" in query:
            return [(1,)]  # Return user ID
        elif "SELECT id FROM sections" in query:
            return [(5,)]  # Return section ID
        else:
            raise SQLAlchemyError("oops")  # Upsert fails

    mock_execute_query.side_effect = side_effect

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis&user_name=TestUser",
                       json={"feedback": "X"})
    assert resp.status_code == 500
    assert "Internal server error" in resp.get_json()["error"]


def test_edit_section_lookup_db_error(client, mock_execute_query):
    """Test edit when section lookup raises SQLAlchemyError (covers lines 152-154)"""
    mock_execute_query.side_effect = SQLAlchemyError("section DB error")

    with client.session_transaction() as sess:
        sess['user_id'] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "X"})
    assert resp.status_code == 500
    assert "Internal server error" in resp.get_json()["error"]


def test_get_user_id_from_request_db_error(client, mock_execute_query):
    """Test get_user_id_from_request re-raises SQLAlchemyError when username supplied (covers lines 46-48)"""
    mock_execute_query.side_effect = SQLAlchemyError("lookup failed")

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis&user_name=TestUser",
                       json={"feedback": "X"})
    # DB error propagates to global handler → 500
    assert resp.status_code == 500
    assert "database error" in resp.get_json()["error"].lower()


def test_route_get_outer_sqlalchemy_error(client, patch_helpers):
    """Test GET route outer except SQLAlchemyError (covers lines 124-126)"""
    fake_fb, fake_ui = patch_helpers
    # Make get_user_info raise SQLAlchemyError (bypassing its internal handler)
    fake_ui.side_effect = SQLAlchemyError("outer db error")

    resp = client.get("/api/devos-feedback?user_name=TestUser")
    assert resp.status_code == 500
    assert "Internal server error" in resp.get_json()["error"]