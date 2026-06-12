import pytest
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend import create_app
from backend.bcssm_backend.exceptions import DatabaseError
from backend.bcssm_backend.utils import get_feedback_by_date, get_user_info
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

# ─── 2) Patch execute_query and execute_readonly_query ──────────────────────────
@pytest.fixture
def mock_write(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_query", m)
    return m

@pytest.fixture
def mock_read(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr("backend.bcssm_backend.utils.execute_readonly_query", m)
    return m

@pytest.fixture(autouse=True)
def mock_execute_query(mock_write, mock_read):
    return mock_write, mock_read

# ─── 3) Unit tests for get_feedback_by_date ──────────────────────────────────────
def test_get_feedback_by_date_success(mock_read):
    mock_read.return_value = [("Minis", "Great job"), ("Majors", None)]
    result = get_feedback_by_date("2025-06-07")
    assert result == {
        "Minis": "Great job",
        "Majors": "No feedback available"
    }

def test_get_feedback_by_date_exception(mock_read):
    mock_read.side_effect = SQLAlchemyError("DB fail")
    with pytest.raises(SQLAlchemyError):
        get_feedback_by_date("2025-06-07")

# ─── 4) Unit tests for get_user_info ────────────────────────────────────────────
def test_get_user_info_found(mock_read):
    mock_read.return_value = [("Alice", "Leader", "Minis")]
    info = get_user_info("Alice")
    assert info == {"name": "Alice", "role": "Leader", "section": "Minis"}

def test_get_user_info_not_found(mock_read):
    mock_read.return_value = []
    info = get_user_info("Bob")
    assert info is None

def test_get_user_info_exception(mock_read):
    mock_read.side_effect = SQLAlchemyError("Oops")
    with pytest.raises(SQLAlchemyError):
        get_user_info("Alice")

# ─── 5) Integration tests for GET /api/devos-feedback ───────────────────────────
@pytest.fixture(autouse=True)
def patch_helpers(monkeypatch):
    fake_fb = MagicMock(return_value={})
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.devos_feedback.get_feedback_by_date",
        fake_fb
    )
    fake_ui = MagicMock(return_value={"name": "TestUser", "role": "Team Member", "section": "Minis"})
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.devos_feedback.get_user_info",
        fake_ui
    )
    return fake_fb, fake_ui

def test_route_default_date_no_user(client, patch_helpers):
    """No session → 401."""
    resp = client.get("/api/devos-feedback")
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]

def test_route_default_date_with_user_via_session(client, patch_helpers):
    """Test route with username from session."""
    fake_fb, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Team Member", "section": "TestSection"}

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"

    resp = client.get("/api/devos-feedback")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "date" in data
    assert data["feedback"] == {}
    assert data["user"]["name"] == "TestUser"
    assert data["can_edit_all"] is False


def test_route_query_param_rejected(client, patch_helpers):
    """Query param user_name is not trusted — session required."""
    resp = client.get("/api/devos-feedback?user_name=TestUser")
    assert resp.status_code == 401


def test_route_with_date_and_leader_via_session(client, patch_helpers):
    """Test route with username via session (backward compatibility)"""
    fake_fb, fake_ui = patch_helpers
    fake_fb.return_value = {"X": "Y"}
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
    assert data["can_edit_all"] is True

def test_route_invalid_user(client, patch_helpers):
    """Session user not found in DB → 400."""
    fake_fb, fake_ui = patch_helpers
    fake_ui.return_value = None

    with client.session_transaction() as sess:
        sess["user_name"] = "NonExistentUser"

    resp = client.get("/api/devos-feedback")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Invalid user" in data["error"]


def test_route_feedback_error(client, patch_helpers):
    """Feedback fetch failure → 500."""
    fake_fb, fake_ui = patch_helpers
    fake_fb.side_effect = DatabaseError("err")
    fake_ui.return_value = {"name": "TestUser", "role": "Team Member", "section": "TestSection"}

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"

    resp = client.get("/api/devos-feedback?date=2025-06-07")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Internal server error"}

# ─── 6) Integration tests for POST /api/devos-feedback/edit ────────────────────
def test_edit_unauthenticated(client):
    """No session → 401."""
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]


def test_edit_feedback_too_long(client):
    """Feedback over 140 chars → 400."""
    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "x" * 141})
    assert resp.status_code == 400
    assert "140 characters" in resp.get_json()["error"]


def test_edit_feedback_exactly_140(client, mock_write):
    """Feedback exactly 140 chars is accepted."""
    mock_write.return_value = [(5,)]

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "x" * 140})
    assert resp.status_code == 200


def test_edit_authenticated_via_session_username(client, mock_write, patch_helpers):
    """Edit with session user_name; editor_id taken from session."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Section Leader", "section": "Minis"}
    mock_write.return_value = [(5,)]

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}


def test_edit_query_param_rejected(client, mock_write):
    """Query param user_name is not trusted — session required."""
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis&user_name=TestUser",
                       json={"feedback": "Test"})
    assert resp.status_code == 401


def test_edit_header_rejected(client, mock_write):
    """X-Current-User header is not trusted — session required."""
    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"},
                       headers={"X-Current-User": "TestUser"})
    assert resp.status_code == 401

def test_edit_editor_id_comes_from_session(client, mock_write):
    """editor_id is taken from session, not resolved via DB lookup."""
    calls = []
    def side_effect(query, params=None):
        calls.append((query, params))
        if "INSERT INTO feedback" in query:
            return [(5,)]
        return None  # pragma: no cover

    mock_write.side_effect = side_effect

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 7

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}
    assert not any("SELECT u.id FROM users" in call[0] for call in calls)
    upsert_call = next(call for call in calls if "INSERT INTO feedback" in call[0])
    assert upsert_call[1]['editor_id'] == 7

def test_edit_missing_params(client):
    """Edit with missing section param → 400."""
    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    assert "Missing date, section, or feedback" in resp.get_json()["error"]


def test_edit_section_not_found(client, mock_write, patch_helpers):
    """RETURNING [] from the combined query → 400 Section not found."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Section Leader", "section": "Minis"}
    mock_write.return_value = []  # INSERT RETURNING [] = section not found

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    assert "Section not found" in resp.get_json()["error"]


def test_edit_success(client, mock_write, patch_helpers):
    """Successful edit — single atomic INSERT...SELECT...RETURNING query."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Section Leader", "section": "Minis"}

    calls = []

    def side_effect(query, params=None):
        calls.append((query, params))
        if "INSERT INTO feedback" in query:
            return [(5,)]
        return None  # pragma: no cover

    mock_write.side_effect = side_effect

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "New"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}
    assert len(calls) == 1  # Only the INSERT...SELECT
    assert any("INSERT INTO feedback" in call[0] for call in calls)


def test_edit_upsert_error(client, mock_write, patch_helpers):
    """Combined INSERT...SELECT query raises → 500."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Section Leader", "section": "Minis"}
    mock_write.side_effect = SQLAlchemyError("oops")

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "X"})
    assert resp.status_code == 500
    assert "Internal server error" in resp.get_json()["error"]


def test_edit_section_lookup_db_error(client, mock_write):
    """Combined INSERT...SELECT raises SQLAlchemyError → 500."""
    mock_write.side_effect = SQLAlchemyError("section DB error")

    with client.session_transaction() as sess:
        sess['user_name'] = 'TestUser'
        sess['user_id'] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "X"})
    assert resp.status_code == 500
    assert "Internal server error" in resp.get_json()["error"]


def test_edit_forbidden_wrong_section(client, mock_write, patch_helpers):
    """Non-privileged user trying to edit another section's feedback → 403."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Leader", "section": "Minis"}

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Majors",
                       json={"feedback": "Test"})
    assert resp.status_code == 403
    assert "Forbidden" in resp.get_json()["error"]


def test_edit_allowed_own_section(client, mock_write, patch_helpers):
    """Non-privileged user editing their own section's feedback → 200."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Leader", "section": "Minis"}
    mock_write.return_value = [(5,)]

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 200


def test_edit_allowed_cross_section_for_section_leader(client, mock_write, patch_helpers):
    """Section Leader editing a different section's feedback → 200 (can_edit_all branch)."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Section Leader", "section": "Minis"}
    mock_write.return_value = [(5,)]

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Majors",
                       json={"feedback": "Test"})
    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}


def test_edit_no_user_id_in_session(client, mock_write, patch_helpers):
    """user_id absent from session → editor_id is None; route proceeds (DB enforces NOT NULL)."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = {"name": "TestUser", "role": "Section Leader", "section": "Minis"}
    mock_write.return_value = [(5,)]

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"  # user_id intentionally omitted

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "X"})
    assert resp.status_code == 200


def test_route_get_outer_sqlalchemy_error(client, patch_helpers):
    """get_user_info raises SQLAlchemyError → 500."""
    _, fake_ui = patch_helpers
    fake_ui.side_effect = SQLAlchemyError("outer db error")

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"

    resp = client.get("/api/devos-feedback")
    assert resp.status_code == 500
    assert "Internal server error" in resp.get_json()["error"]


def test_edit_editor_info_db_error(client, mock_write, patch_helpers):
    """get_user_info raises SQLAlchemyError during editor info lookup → 500."""
    _, fake_ui = patch_helpers
    fake_ui.side_effect = SQLAlchemyError("editor info lookup failed")

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 500
    assert "Internal server error" in resp.get_json()["error"]


def test_edit_editor_info_not_found(client, mock_write, patch_helpers):
    """get_user_info returns None for editor → 400 Invalid user."""
    _, fake_ui = patch_helpers
    fake_ui.return_value = None

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"
        sess["user_id"] = 1

    resp = client.post("/api/devos-feedback/edit?date=2025-06-07&section=Minis",
                       json={"feedback": "Test"})
    assert resp.status_code == 400
    assert "Invalid user" in resp.get_json()["error"]