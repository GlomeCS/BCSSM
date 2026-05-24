# backend/tests/test_users_routes.py
# Updated tests for new cache integration where utils functions handle caching

import pytest
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from backend.bcssm_backend import create_app
from backend.bcssm_backend.exceptions import AuthenticationError
from unittest.mock import MagicMock, patch

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

# ─── 2) Updated fixture: patch underlying helpers (no route-level cache mocking) ──
@pytest.fixture(autouse=True)
def patch_helpers(monkeypatch):
    fake_get_by_section = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.get_users_by_section",
        fake_get_by_section
    )
    fake_get_duty = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.get_user_duty",
        fake_get_duty
    )
    fake_get_all = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.get_all_users",
        fake_get_all
    )
    fake_exec = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.execute_query",
        fake_exec
    )
    fake_cache = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.cache",
        fake_cache
    )
    fake_clear_cache = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.clear_user_cache",
        fake_clear_cache
    )
    fake_authenticate_user = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.authenticate_user",
        fake_authenticate_user
    )
    fake_cache_user_login = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.cache_user_login",
        fake_cache_user_login
    )
    fake_evict_user_login_cache = MagicMock()
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.users.evict_user_login_cache",
        fake_evict_user_login_cache
    )
    return {
        "by_section": fake_get_by_section,
        "duty": fake_get_duty,
        "all_users": fake_get_all,
        "execute": fake_exec,
        "cache": fake_cache,
        "clear_cache": fake_clear_cache,
        "authenticate_user": fake_authenticate_user,
        "cache_user_login": fake_cache_user_login,
        "evict_user_login_cache": fake_evict_user_login_cache,
    }

# ─── 3) GET /users-by-section ────────────────────────────────────────────────────
def test_users_by_section_success(client, patch_helpers):
    """Test users by section - now uses utils function with built-in caching"""
    ph = patch_helpers
    # Mock utils function returns data directly (already cached internally)
    ph["by_section"].return_value = [{"name": "Alice", "role": "Leader"}]

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.get_json() == {"users": [{"name": "Alice", "role": "Leader"}]}
    
    # Verify utils function was called (caching happens inside utils)
    ph["by_section"].assert_called_once_with("Minors")
    # Route-level cache operations no longer happen
    assert not ph["cache"].get.called
    assert not ph["cache"].set.called

def test_users_by_section_error_response(client, patch_helpers):
    """Test users by section when utils returns error dict"""
    ph = patch_helpers
    # Mock utils function returns error (as per utils.py implementation)
    ph["by_section"].return_value = {"error": "Failed to fetch users by section"}

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data
    assert "Failed to fetch users for this section" in data["error"]

def test_users_by_section_missing_param(client, patch_helpers):
    resp = client.get("/users-by-section")  # Missing section parameter
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "Missing parameters" in data["error"]

def test_users_by_section_exception(client, patch_helpers):
    """Test exception handling in route"""
    ph = patch_helpers
    ph["by_section"].side_effect = SQLAlchemyError("DB error")

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

# ─── 4) GET /user-duty ────────────────────────────────────────────────────────────
def test_user_duty_success(client, patch_helpers):
    """Test user duty requires session-based auth."""
    ph = patch_helpers
    ph["duty"].return_value = {"user": "Alice", "duty": "Cleaning"}

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/user-duty")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": "Alice", "duty": "Cleaning"}
    ph["duty"].assert_called_once_with("Alice")
    assert not ph["cache"].get.called
    assert not ph["cache"].set.called


def test_user_duty_query_param_rejected(client, patch_helpers):
    """Query param user is no longer trusted — must return 400."""
    ph = patch_helpers
    ph["duty"].return_value = {"user": "Alice", "duty": "Cleaning"}

    resp = client.get("/user-duty?user=Alice")
    assert resp.status_code == 400
    ph["duty"].assert_not_called()


def test_user_duty_error_response(client, patch_helpers):
    """Test user duty when utils returns error dict."""
    ph = patch_helpers
    ph["duty"].return_value = {"error": "User not found or no duty assigned"}

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/user-duty")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "error" in data
    assert "User not found or no duty assigned" in data["error"]


def test_user_duty_missing_param(client, patch_helpers):
    """No session → 400."""
    resp = client.get("/user-duty")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "Username required" in data["error"]


def test_user_duty_exception(client, patch_helpers):
    """Test exception handling in route."""
    ph = patch_helpers
    ph["duty"].side_effect = SQLAlchemyError("Oops")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/user-duty")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

# ─── 6) GET /get-selected-user ───────────────────────────────────────────────────
def test_get_selected_user_with_cache(client, patch_helpers):
    ph = patch_helpers
    # Mock cached user data
    ph["cache"].get.return_value = {
        "id": 42,
        "name": "Zed", 
        "role": "Leader",
        "section_name": "Minors",
        "is_leader": True
    }
    
    with client.session_transaction() as sess:
        sess["user_name"] = "Zed"
    
    resp = client.get("/get-selected-user")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"] == "Zed"
    assert "user_data" in data
    assert data["user_data"]["name"] == "Zed"

def test_get_selected_user_no_cache(client, patch_helpers):
    ph = patch_helpers
    # Mock cache miss
    ph["cache"].get.return_value = None
    
    with client.session_transaction() as sess:
        sess["user_name"] = "Zed"
    
    resp = client.get("/get-selected-user")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"] == "Zed"
    assert "user_data" not in data

def test_get_selected_user_cache_error(client, patch_helpers):
    """Test cache error handling doesn't break the response"""
    ph = patch_helpers
    ph["cache"].get.side_effect = RedisError("Cache failed")
    
    with client.session_transaction() as sess:
        sess["user_name"] = "Zed"
    
    resp = client.get("/get-selected-user")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"] == "Zed"
    # Should fall back to basic response when cache fails

def test_get_selected_user_none(client, patch_helpers):
    resp = client.get("/get-selected-user")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": None}

# ─── 7) GET /get-users ────────────────────────────────────────────────────────────
def test_get_users_success(client, patch_helpers):
    """Test get users - now uses utils function with built-in caching"""
    ph = patch_helpers
    # Mock utils function returns data directly (already cached internally)
    ph["all_users"].return_value = ["Alice", "Bob"]

    resp = client.get("/get-users")
    assert resp.status_code == 200
    assert resp.get_json() == {"users": ["Alice", "Bob"]}
    
    # Verify utils function was called (caching happens inside utils)
    ph["all_users"].assert_called_once()
    # Route-level cache operations no longer happen
    assert not ph["cache"].get.called
    assert not ph["cache"].set.called

def test_get_users_error(client, patch_helpers):
    ph = patch_helpers
    ph["all_users"].side_effect = SQLAlchemyError("Database error")

    resp = client.get("/get-users")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

# ─── 8) POST /logout ─────────────────────────────────────────────────────────────
def test_logout(client, patch_helpers):
    """Test successful logout - fixed for JSON content type"""
    ph = patch_helpers
    
    with client.session_transaction() as sess:
        sess["user_name"] = "Someone"
    
    # Send JSON request instead of form data
    resp = client.post("/logout", json={}, content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "User logged out successfully!"}
    
    # Verify session is cleared
    with client.session_transaction() as sess:
        assert sess.get("user_name") is None
    
    # Verify cache cleanup was attempted
    ph["cache"].delete.assert_called()
    delete_calls = ph["cache"].delete.call_args_list
    assert any("user:data:Someone" in str(call) for call in delete_calls)

def test_logout_cache_error_handling(client, patch_helpers):
    """Test that cache errors don't break logout - fixed for JSON content type"""
    ph = patch_helpers
    ph["cache"].delete.side_effect = RedisError("Cache failed")
    
    with client.session_transaction() as sess:
        sess["user_name"] = "Someone"
    
    # Send JSON request instead of form data
    resp = client.post("/logout", json={}, content_type='application/json')
    # Should still succeed even if cache clearing fails
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "User logged out successfully!"}

def test_logout_no_user(client, patch_helpers):
    """Test logout without user in session - fixed for JSON content type"""
    ph = patch_helpers
    
    # Send JSON request instead of form data
    resp = client.post("/logout", json={}, content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "User logged out successfully!"}

# ─── 9) GET /cache-stats ─────────────────────────────────────────────────────────
def test_cache_stats_healthy(client, patch_helpers):
    ph = patch_helpers
    # Mock successful cache health check
    ph["cache"].get.return_value = "ok"

    resp = client.get("/cache-stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["cache_status"] == "healthy"
    assert data["cache_type"] == "RedisCache"
    # Check for enhanced cache stats
    assert "cached_functions" in data
    assert "management" in data

def test_cache_stats_unhealthy(client, patch_helpers):
    ph = patch_helpers
    # Mock cache failure
    ph["cache"].set.side_effect = RedisError("Redis connection failed")

    resp = client.get("/cache-stats")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["cache_status"] == "unhealthy"

# ─── 11) GET /api/auth/validate ─────────────────────────────────────────────────
def test_validate_user_success_with_session(client, patch_helpers):
    """Test /api/auth/validate succeeds with a valid session."""
    ph = patch_helpers
    ph["execute"].return_value = [(44, "Charlie", "Admin", "Unassigned")]

    with client.session_transaction() as sess:
        sess["user_name"] = "Charlie"

    resp = client.get("/api/auth/validate")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_valid"] is True
    assert data["user_name"] == "Charlie"
    assert data["role"] == "Admin"
    assert data["section"] == "Unassigned"
    assert data["is_leader"] is True


def test_validate_user_query_param_rejected(client, patch_helpers):
    """Query param user_name is not trusted — must return 400."""
    ph = patch_helpers
    ph["execute"].return_value = [(42, "Alice", "Section Leader", "Minors")]

    resp = client.get("/api/auth/validate?user_name=Alice")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["is_valid"] is False


def test_validate_user_header_rejected(client, patch_helpers):
    """X-Current-User header is not trusted — must return 400."""
    ph = patch_helpers
    ph["execute"].return_value = [(43, "Bob", "Team Member", "Majors")]

    resp = client.get("/api/auth/validate", headers={"X-Current-User": "Bob"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["is_valid"] is False


def test_validate_user_team_leader_role(client, patch_helpers):
    """Team Leader role is identified as a leader."""
    ph = patch_helpers
    ph["execute"].return_value = [(45, "David", "Team Leader", "Micros")]

    with client.session_transaction() as sess:
        sess["user_name"] = "David"

    resp = client.get("/api/auth/validate")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_valid"] is True
    assert data["user_name"] == "David"
    assert data["role"] == "Team Leader"
    assert data["section"] == "Micros"
    assert data["is_leader"] is True


def test_validate_user_no_username_provided(client, patch_helpers):
    """No session → 400."""
    resp = client.get("/api/auth/validate")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["is_valid"] is False
    assert "No username provided" in data["error"]


def test_validate_user_invalid_user(client, patch_helpers):
    """User not in DB → 400."""
    ph = patch_helpers
    ph["execute"].return_value = []

    with client.session_transaction() as sess:
        sess["user_name"] = "NonExistentUser"

    resp = client.get("/api/auth/validate")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["is_valid"] is False
    assert "Invalid user" in data["error"]


def test_validate_user_database_error(client, patch_helpers):
    """DB error → 500."""
    ph = patch_helpers
    ph["execute"].side_effect = SQLAlchemyError("Database connection failed")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.get("/api/auth/validate")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["is_valid"] is False
    assert "Validation failed" in data["error"]


def test_validate_user_user_without_section(client, patch_helpers):
    """User with no section returns is_valid=True and section=None."""
    ph = patch_helpers
    ph["execute"].return_value = [(46, "Eve", "Team Member", None)]

    with client.session_transaction() as sess:
        sess["user_name"] = "Eve"

    resp = client.get("/api/auth/validate")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_valid"] is True
    assert data["user_name"] == "Eve"
    assert data["role"] == "Team Member"
    assert data["section"] is None
    assert data["is_leader"] is False


def test_validate_user_session_takes_priority(client, patch_helpers):
    """Session username is used even when query param and header are also present."""
    ph = patch_helpers
    ph["execute"].return_value = [(47, "SessionUser", "Section Leader", "Minis")]

    with client.session_transaction() as sess:
        sess["user_name"] = "SessionUser"

    resp = client.get("/api/auth/validate?user_name=QueryUser",
                      headers={"X-Current-User": "HeaderUser"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user_name"] == "SessionUser"


def test_validate_user_execute_query_called_correctly(client, patch_helpers):
    """execute_query receives correct SQL and params."""
    ph = patch_helpers
    ph["execute"].return_value = [(48, "TestUser", "Team Member", "TestSection")]

    with client.session_transaction() as sess:
        sess["user_name"] = "TestUser"

    resp = client.get("/api/auth/validate")
    assert resp.status_code == 200

    ph["execute"].assert_called_once()
    call_args = ph["execute"].call_args
    sql, params = call_args[0]

    assert "SELECT u.id, u.name, u.role, s.name AS section_name" in sql
    assert "FROM users u" in sql
    assert "LEFT JOIN sections s ON u.section_id = s.id" in sql
    assert "WHERE u.name = :user_name" in sql
    assert params == {"user_name": "TestUser"}

# ─── 12) NEW: Admin endpoints ────────────────────────────────────────────────────
def test_clear_user_cache_endpoint(client, patch_helpers):
    """Test the new admin cache clearing endpoint"""
    ph = patch_helpers
    
    resp = client.post("/admin/clear-user-cache")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "cleared successfully" in data["message"]
    
    # Verify clear_user_cache was called
    ph["clear_cache"].assert_called_once()

def test_clear_user_cache_endpoint_error(client, patch_helpers):
    """Test cache clearing endpoint error handling"""
    ph = patch_helpers
    ph["clear_cache"].side_effect = RedisError("Cache clear failed")
    
    resp = client.post("/admin/clear-user-cache")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["success"] is False

def test_update_user_endpoint(client, patch_helpers):
    """Test the new user update endpoint"""
    ph = patch_helpers

    resp = client.put("/admin/users/123", json={"name": "New Name"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

    # Verify clear_user_cache was called after update
    ph["clear_cache"].assert_called_once()


def test_update_user_no_data(client, patch_helpers):
    """Test update_user returns 400 when JSON body is empty (covers line 330)"""
    resp = client.put("/admin/users/123", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "No data provided"


def test_update_user_db_error(client, patch_helpers):
    """Test update_user returns 500 when clear_user_cache raises SQLAlchemyError (covers lines 343-345)"""
    ph = patch_helpers
    ph["clear_cache"].side_effect = SQLAlchemyError("cache clear failed")

    resp = client.put("/admin/users/123", json={"name": "New Name"})
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["success"] is False


def test_inject_user_state_redis_error(app, patch_helpers):
    """Context processor falls back to session when cache.get raises RedisError."""
    ph = patch_helpers
    ph["cache"].get.side_effect = RedisError("Redis down")

    with app.test_request_context('/'):
        from flask import session
        session['user_name'] = 'TestUser'
        processors = app.template_context_processors.get(None, [])
        inject_func = next(
            (p for p in processors if p.__name__ == 'inject_user_state'), None
        )
        assert inject_func is not None, "inject_user_state context processor not found"
        result = inject_func()
        assert result['is_logged_in'] is True
        # After RedisError, falls back to session (which has no extra data)
        assert result['user_section'] is None


# ─── 13) POST /api/auth/login ─────────────────────────────────────────────────
def test_api_login_success(client, patch_helpers):
    """Valid user_name returns session cookie and user data."""
    ph = patch_helpers
    ph["authenticate_user"].return_value = {
        "id": 1, "name": "Alice", "role": "Section Leader",
        "section_name": "Minis", "is_leader": True,
    }

    resp = client.post("/api/auth/login", json={"user_name": "Alice"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["user_name"] == "Alice"
    assert data["role"] == "Section Leader"
    assert data["section"] == "Minis"
    assert data["is_leader"] is True

    with client.session_transaction() as sess:
        assert sess["user_name"] == "Alice"
        assert sess["user_id"] == 1


def test_api_login_calls_cache_user_login(client, patch_helpers):
    """Successful login calls cache_user_login with the user dict."""
    ph = patch_helpers
    user = {"id": 2, "name": "Bob", "role": "Team Member",
            "section_name": "Seniors", "is_leader": False}
    ph["authenticate_user"].return_value = user

    client.post("/api/auth/login", json={"user_name": "Bob"})

    ph["cache_user_login"].assert_called_once_with(user)


def test_api_login_name_with_apostrophe(client, patch_helpers):
    """Names containing apostrophes are passed verbatim to authenticate_user."""
    ph = patch_helpers
    ph["authenticate_user"].return_value = {
        "id": 10, "name": "O'Reilly", "role": "Team Member",
        "section_name": "Minis", "is_leader": False,
    }

    resp = client.post("/api/auth/login", json={"user_name": "O'Reilly"})
    assert resp.status_code == 200

    called_with = ph["authenticate_user"].call_args[0][0]
    assert called_with == "O'Reilly"


def test_api_login_missing_user_name(client, patch_helpers):
    """POST body without user_name → 400."""
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 400
    assert "user_name required" in resp.get_json()["error"]


def test_api_login_invalid_user(client, patch_helpers):
    """authenticate_user raises AuthenticationError → 401."""
    ph = patch_helpers
    ph["authenticate_user"].side_effect = AuthenticationError("Invalid user")

    resp = client.post("/api/auth/login", json={"user_name": "Ghost"})
    assert resp.status_code == 401
    assert "Invalid user" in resp.get_json()["error"]


def test_api_login_db_error(client, patch_helpers):
    """authenticate_user raises SQLAlchemyError → 500."""
    ph = patch_helpers
    ph["authenticate_user"].side_effect = SQLAlchemyError("db down")

    resp = client.post("/api/auth/login", json={"user_name": "Alice"})
    assert resp.status_code == 500
    assert "internal error" in resp.get_json()["error"].lower()


def test_api_login_non_leader_role(client, patch_helpers):
    """Team Member role results in is_leader=False."""
    ph = patch_helpers
    ph["authenticate_user"].return_value = {
        "id": 4, "name": "Dave", "role": "Team Member",
        "section_name": "Minis", "is_leader": False,
    }

    resp = client.post("/api/auth/login", json={"user_name": "Dave"})
    assert resp.status_code == 200
    assert resp.get_json()["is_leader"] is False


# ─── 14) POST /api/auth/logout ────────────────────────────────────────────────
def test_api_logout_clears_session(client, patch_helpers):
    """Logout clears the server-side session."""
    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"
        sess["user_id"] = 1

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with client.session_transaction() as sess:
        assert "user_name" not in sess


def test_api_logout_evicts_cache(client, patch_helpers):
    """Logout calls evict_user_login_cache with the session username."""
    ph = patch_helpers
    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    client.post("/api/auth/logout")
    ph["evict_user_login_cache"].assert_called_once_with("Alice")


def test_api_logout_cache_error_does_not_fail(client, patch_helpers):
    """evict_user_login_cache swallows RedisError internally — response still 200."""
    ph = patch_helpers
    ph["evict_user_login_cache"].return_value = None  # simulates silent failure

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_api_logout_without_session(client, patch_helpers):
    """Logout with no active session → still 200, evict_user_login_cache not called."""
    ph = patch_helpers

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    ph["evict_user_login_cache"].assert_not_called()