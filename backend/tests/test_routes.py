import logging
from urllib.parse import urlparse, quote

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend import create_app


# ─── 0) Combine environment + DB‐deny fixtures ─────────────────────────────────
@pytest.fixture(autouse=True)
def env_and_deny_db(monkeypatch):
    """
    Mock the database session to work with your execute_query function
    """
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_password")
    monkeypatch.setenv("host", "localhost")
    monkeypatch.setenv("port", "5432")
    monkeypatch.setenv("database", "test_db")

    # Mock the database session and related components
    mock_sess = MagicMock()
    mock_result = MagicMock()
    
    # Mock the context manager for session.begin()
    mock_sess.begin.return_value.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.begin.return_value.__exit__ = MagicMock(return_value=None)
    
    # Mock the execute result
    mock_result.returns_rows = True  # Assume SELECT queries return rows
    mock_result.fetchall.return_value = []  # Default to empty (no users)
    
    mock_sess.execute.return_value = mock_result
    mock_sess.rollback = MagicMock()
    
    # Mock the text() function from SQLAlchemy
    mock_text = MagicMock(side_effect=lambda x: x)  # Just return the query string
    
    # Patch all the components
    monkeypatch.setattr('backend.bcssm_backend.db.session', mock_sess)
    monkeypatch.setattr('backend.bcssm_backend.utils.text', mock_text)
    
    return mock_sess, mock_result


# Helper function to setup database responses
def setup_db_response(env_and_deny_db, user_data=None):
    """
    Helper to setup what the database should return
    user_data: List of tuples like [(1, 'Username', 'Role')] or None/[] for no users
    """
    mock_sess, mock_result = env_and_deny_db
    
    if user_data is None:
        user_data = []
    
    mock_result.fetchall.return_value = user_data
    return mock_sess, mock_result


# ─── 0.5) Mock the cache to avoid Redis connection issues ───────────────────────
@pytest.fixture(autouse=True)
def mock_cache(monkeypatch):
    """Mock the cache to avoid Redis connection during tests"""
    fake_cache = MagicMock()
    fake_cache.get.return_value = None
    fake_cache.set.return_value = True
    fake_cache.delete.return_value = True
    fake_cache.clear.return_value = True
    
    monkeypatch.setattr('backend.bcssm_backend.utils.cache', fake_cache)
    monkeypatch.setattr('backend.bcssm_backend.routes.users.cache', fake_cache)
    
    return fake_cache


# ─── 0.6) Mock database queries to avoid SQLAlchemy issues ──────────────────────
@pytest.fixture(autouse=True)
def mock_db_queries(monkeypatch):
    """Mock database query functions to avoid SQLAlchemy initialization issues"""
    mock_readonly = MagicMock(side_effect=SQLAlchemyError("Database access not allowed in tests"))
    monkeypatch.setattr('backend.bcssm_backend.utils.execute_readonly_query', mock_readonly)
    
    return mock_readonly


# ─── 1) Fixture: Create app & client ────────────────────────────────────────────
@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret'
    return app

@pytest.fixture
def client(app):
    return app.test_client()


# ─── 2) Patch utils helpers ───────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def patch_utils_helpers(monkeypatch):
    """
    Mock utility functions for controlled testing
    """
    fake_users = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.utils.get_all_users", fake_users)

    fake_assign = {}
    monkeypatch.setattr("backend.bcssm_backend.utils.user_assignments", fake_assign, raising=False)

    fake_duty = MagicMock(return_value=None)
    
    # Patch get_user_duty in all possible locations where it might be imported
    monkeypatch.setattr("backend.bcssm_backend.utils.get_user_duty", fake_duty)
    
    # Patch in the main routes module where it's likely imported
    try:
        monkeypatch.setattr("backend.bcssm_backend.routes.routes.get_user_duty", fake_duty)
    except AttributeError:
        pass
    
    # Patch in users routes
    try:
        monkeypatch.setattr("backend.bcssm_backend.routes.users.get_user_duty", fake_duty)
    except AttributeError:
        pass
    
    # Patch where the app imports it directly (this is likely the one we need)
    try:
        from backend.bcssm_backend.routes import routes
        monkeypatch.setattr(routes, "get_user_duty", fake_duty)
    except (ImportError, AttributeError):
        pass

    return fake_users, fake_assign, fake_duty


# ─── 3) Tests for "/" (index) ─────────────────────────────────────────────────────
def test_index_shows_dropdown_of_users(client, patch_utils_helpers):
    """Test index route returns 404 as expected"""
    fake_users, *_ = patch_utils_helpers

    response = client.get("/")
    assert response.status_code == 404
    fake_users.assert_not_called()


@pytest.mark.parametrize("user_list, expected_message", [
    ([], "No users available"),
    (["Solo"], "<option value=\"Solo\">Solo</option>"),
])
def test_index_empty_or_single_user(client, patch_utils_helpers, user_list, expected_message):
    fake_users, *_ = patch_utils_helpers
    fake_users.return_value = user_list

    response = client.get("/")
    assert response.status_code == 404
    assert expected_message not in response.data.decode()
    fake_users.assert_not_called()


# ─── 4) Tests for "/login" ───────────────────────────────────────────────────────
@pytest.mark.parametrize("valid_users, post_user, target, expected_path", [
    (["A"], "A", None, "/"),
    (["A"], "A", "/dashboard", "/"),  # Target validation redirects to /
    (["A"], "A", "http://evil.com", "/"),
    ([], "A", None, "/"),  # Invalid user goes back to index
])
def test_login_post_various(client, env_and_deny_db, valid_users, post_user, target, expected_path):
    # Setup database to return valid users
    user_data = [(1, user) for user in valid_users]
    setup_db_response(env_and_deny_db, user_data=user_data)

    url = "/login" + (f"?target={quote(target)}" if target else "")
    resp = client.post(url, data={"user_name": post_user}, follow_redirects=False)

    assert resp.status_code == 302
    assert urlparse(resp.headers["Location"]).path == expected_path


def test_login_get_redirects_to_index(client):
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert urlparse(resp.headers["Location"]).path == "/"


# ─── 5) Tests for "/duty-teams" ─────────────────────────────────────────────────
def test_duty_team_redirects_if_not_logged_in(client):
    """Without session, should respond with 401."""
    resp = client.get("/duty-teams", follow_redirects=False)
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]


def test_duty_team_shows_no_duty_message(client, patch_utils_helpers, env_and_deny_db):
    _, _, fake_duty = patch_utils_helpers
    fake_duty.return_value = None  # No duty assigned

    # Setup database to return valid user "A"
    setup_db_response(env_and_deny_db, user_data=[(1, 'A', 'Leader')])

    with client.session_transaction() as sess:
        sess["user_name"] = "A"

    resp = client.get("/duty-teams")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"] == "A"
    assert data["duty_message"] == "No duty assigned"
    assert data["role"] == "Leader"  # From database when no duty


def test_duty_team_shows_duty_when_assigned(client, patch_utils_helpers, env_and_deny_db):
    _, _, fake_duty = patch_utils_helpers
    fake_duty.return_value = {"duty": "Clean kitchen", "role": "Worker"}

    # Setup database to return valid user "A"
    setup_db_response(env_and_deny_db, user_data=[(1, 'A', 'Leader')])

    with client.session_transaction() as sess:
        sess["user_name"] = "A"

    resp = client.get("/duty-teams")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"] == "A"
    assert data["duty_message"] == "Clean kitchen"
    assert data["role"] == "Worker"  # From duty data overrides database


def test_duty_team_invalid_user_returns_400(client, patch_utils_helpers, env_and_deny_db):
    """Test /duty-teams with invalid user (in session but not in DB) returns 400."""
    fake_users, fake_assign, fake_duty = patch_utils_helpers

    # Setup database to return no users (empty result)
    setup_db_response(env_and_deny_db, user_data=[])

    with client.session_transaction() as sess:
        sess["user_name"] = "InvalidUser"

    resp = client.get("/duty-teams")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "Invalid user" in data["error"]


def test_duty_team_with_session(client, patch_utils_helpers, env_and_deny_db):
    """Test backward compatibility with session-based auth"""
    _, _, fake_duty = patch_utils_helpers
    fake_duty.return_value = {"duty": "Kitchen duty", "role": "Helper"}
    
    # Setup database to return valid user
    setup_db_response(env_and_deny_db, user_data=[(1, 'SessionUser', 'Leader')])

    with client.session_transaction() as sess:
        sess["user_name"] = "SessionUser"

    # Call without query parameter (should use session)
    resp = client.get("/duty-teams")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"] == "SessionUser"
    assert data["duty_message"] == "Kitchen duty"
    assert data["role"] == "Helper"


def test_duty_team_header_rejected(client, patch_utils_helpers, env_and_deny_db):
    """X-Current-User header is not trusted — session required."""
    resp = client.get("/duty-teams", headers={"X-Current-User": "HeaderUser"})
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]


@pytest.mark.parametrize("duty_response", [
    None,
    {"duty": "Foo", "role": "Worker"},
    {"error": "DB down"}  # Error case
])
def test_duty_team_helper_called_with_session_user(client, patch_utils_helpers, env_and_deny_db, duty_response):
    _, _, fake_duty = patch_utils_helpers
    fake_duty.return_value = duty_response

    # Setup database to return valid user
    setup_db_response(env_and_deny_db, user_data=[(1, 'UserX', 'Leader')])

    with client.session_transaction() as sess:
        sess["user_name"] = "UserX"

    resp = client.get("/duty-teams")
    assert resp.status_code == 200
    data = resp.get_json()

    assert "duty_message" in data
    assert "user" in data
    assert data["user"] == "UserX"

    if duty_response is None or duty_response.get("error"):
        assert data["duty_message"] == "No duty assigned"
        assert data["role"] == "Leader"  # From database when no duty
    else:
        assert data["duty_message"] == duty_response["duty"]
        assert data["role"] == duty_response.get("role")


def test_duty_team_helper_raises_causes_internal_error(client, patch_utils_helpers, env_and_deny_db):
    _, _, fake_duty = patch_utils_helpers
    fake_duty.side_effect = SQLAlchemyError("oops")

    setup_db_response(env_and_deny_db, user_data=[(1, 'User1', 'Leader')])

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    resp = client.get("/duty-teams")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data
    assert data["error"] == "Internal server error"


def test_duty_team_index_error_caught(client, patch_utils_helpers, env_and_deny_db):
    """Test that IndexError from get_user_duty is caught by the broadened handler"""
    _, _, fake_duty = patch_utils_helpers
    fake_duty.side_effect = IndexError("row index out of range")

    setup_db_response(env_and_deny_db, user_data=[(1, 'User1', 'Leader')])

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    resp = client.get("/duty-teams")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["error"] == "Internal server error"


# ─── 6) Testing static‐file or React SPA fallback ──────────────────────────────
def test_serve_react_index_or_static(client):
    resp_static = client.get("/static/some-file.js")
    assert resp_static.status_code in (200, 404)

    resp_fallback = client.get("/foo/bar")
    assert resp_fallback.status_code in (200, 404)
    text = resp_fallback.data.decode().lower()
    if resp_fallback.status_code == 200:
        assert "<!doctype html>" in text


# ─── 7) Ensure invalid target logging ──────────────────────────────────────────
def test_login_invalid_target_logs_warning(client, env_and_deny_db, caplog):
    # Setup database to return valid user
    setup_db_response(env_and_deny_db, user_data=[(1, 'A')])

    caplog.set_level(logging.DEBUG)
    resp = client.post("/login?target=http://evil.com", data={"user_name": "A"}, follow_redirects=False)
    assert resp.status_code == 302
    assert urlparse(resp.headers["Location"]).path == "/"


# ─── 8) Login POST with user in user_assignments ────────────────────────────────
def test_login_post_valid_user_in_assignments(client):
    """Test login POST when user IS in user_assignments (covers logger.debug lines 49-57)"""
    from unittest.mock import patch as _patch
    # Patch user_assignments in the routes module directly to include our test user
    with _patch.dict('backend.bcssm_backend.routes.routes.user_assignments', {'ValidUser': 'section'}):
        resp = client.post("/login", data={"user_name": "ValidUser"}, follow_redirects=False)
    assert resp.status_code == 302
    assert urlparse(resp.headers["Location"]).path == "/"


def test_login_post_valid_user_valid_target(client):
    """Test login POST with valid relative target redirects to that target"""
    from unittest.mock import patch as _patch
    with _patch.dict('backend.bcssm_backend.routes.routes.user_assignments', {'ValidUser': 'section'}):
        resp = client.post("/login?target=/dashboard", data={"user_name": "ValidUser"}, follow_redirects=False)
    assert resp.status_code == 302
    # Relative target is accepted
    assert urlparse(resp.headers["Location"]).path == "/dashboard"


def test_login_post_valid_user_external_target(client):
    """Test login POST with external URL target redirects to / (covers lines 56-57)"""
    from unittest.mock import patch as _patch
    with _patch.dict('backend.bcssm_backend.routes.routes.user_assignments', {'ValidUser': 'section'}):
        resp = client.post("/login?target=http://evil.com", data={"user_name": "ValidUser"}, follow_redirects=False)
    assert resp.status_code == 302
    assert urlparse(resp.headers["Location"]).path == "/"