import pytest
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
    mock_execute_query.side_effect = Exception("DB fail")
    result, error = get_feedback_by_date("2025-06-07")
    assert result is None
    assert "DB fail" in error

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
    mock_execute_query.side_effect = Exception("Oops")
    info = get_user_info("Alice")
    assert info is None

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

def test_route_default_date(client, patch_helpers):
    fake_fb, fake_ui = patch_helpers
    resp = client.get("/api/devos-feedback")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "date" in data
    assert data["feedback"] == {}
    assert data["user"] is None
    assert data["is_leader"] is None

def test_route_with_date_and_leader(client, patch_helpers):
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

def test_route_feedback_error(client, patch_helpers):
    fake_fb, _ = patch_helpers
    fake_fb.return_value = (None, "err")
    resp = client.get("/api/devos-feedback?date=2025-06-07")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Internal server error"}

# ─── 6) Integration tests for POST /api/devos-feedback/edit ────────────────────
def test_edit_unauthenticated(client):
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "User not authenticated"}

def test_edit_missing_params(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    assert "Missing date, section, or feedback" in resp.get_json()["error"]

def test_edit_section_not_found(client, mock_execute_query):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    mock_execute_query.return_value = []
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    assert "Section 'Minis' not found" in resp.get_json()["error"]

def test_edit_success(client, mock_execute_query):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    calls = []
    def side_effect(query, params=None):
        calls.append((query, params))
        return [(1,)] if len(calls) == 1 else None
    mock_execute_query.side_effect = side_effect
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "New"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}
    assert len(calls) == 2
    assert calls[0][0].strip().startswith("SELECT id FROM sections")
    assert "INSERT INTO feedback" in calls[1][0]

def test_edit_upsert_error(client, mock_execute_query):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    def side_effect(query, params=None):
        if "SELECT id FROM sections" in query:
            return [(5,)]
        raise Exception("oops")
    mock_execute_query.side_effect = side_effect
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "X"})
    assert resp.status_code == 500
    assert "oops" in resp.get_json()["error"]