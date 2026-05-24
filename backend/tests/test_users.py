# backend/tests/test_users_routes.py
# Updated tests for new cache integration where utils functions handle caching

import pytest
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from backend.bcssm_backend import create_app
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
    # Keep cache mock for session-related caching only
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
    return {
        "by_section": fake_get_by_section,
        "duty": fake_get_duty,
        "all_users": fake_get_all,
        "execute": fake_exec,
        "cache": fake_cache,
        "clear_cache": fake_clear_cache
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

# ─── 5) POST /select-user ───────────────────────────────────────────────────────
def test_select_user_success(client, patch_helpers):
    ph = patch_helpers
    # Mock successful user lookup
    ph["execute"].return_value = [(42, "Alice", "Section Leader", "Minors")]

    resp = client.post("/select-user", json={"user_name": "Alice"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "User Alice successfully selected."
    assert data["is_logged_in"] is True
    assert data["is_leader"] is True
    assert data["user_section"] == "Minors"

    # Verify session data
    with client.session_transaction() as sess:
        assert sess["user_name"] == "Alice"
        assert sess["user_id"] == 42
        assert sess["user_section"] == "Minors"
        assert sess["is_leader"] is True

    # Verify cache operations for user data (this still happens in routes)
    ph["cache"].set.assert_called()
    cache_call_args = ph["cache"].set.call_args_list
    # Should cache user data
    user_cache_call = next((call for call in cache_call_args 
                           if call[0][0] == "user:data:Alice"), None)
    assert user_cache_call is not None

def test_select_user_invalid(client, patch_helpers):
    ph = patch_helpers
    # Mock user not found in database
    ph["execute"].return_value = []

    resp = client.post("/select-user", json={"user_name": "Charlie"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid user selected"

    # Verify session is not set
    with client.session_transaction() as sess:
        assert sess.get("user_name") is None

def test_select_user_missing_name(client, patch_helpers):
    resp = client.post("/select-user", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "User name required."

def test_select_user_error(client, patch_helpers):
    ph = patch_helpers
    ph["execute"].side_effect = SQLAlchemyError("DB connection failed")

    resp = client.post("/select-user", json={"user_name": "Alice"})
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

def test_select_user_cache_error_handling(client, patch_helpers):
    """Test that cache errors don't break user selection"""
    ph = patch_helpers
    ph["execute"].return_value = [(42, "Alice", "Section Leader", "Minors")]
    # Make cache.set fail
    ph["cache"].set.side_effect = RedisError("Cache failed")

    resp = client.post("/select-user", json={"user_name": "Alice"})
    # Should still succeed even if caching fails
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "User Alice successfully selected."

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
    ph["execute"].return_value = [(1, "Alice", "Section Leader", "Minis")]

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


def test_api_login_sets_cache(client, patch_helpers):
    """Successful login writes user data to Redis cache."""
    ph = patch_helpers
    ph["execute"].return_value = [(2, "Bob", "Team Member", "Seniors")]

    client.post("/api/auth/login", json={"user_name": "Bob"})

    ph["cache"].set.assert_called_once()
    call_kwargs = ph["cache"].set.call_args
    key = call_kwargs[0][0]
    assert key == "user:data:Bob"


def test_api_login_cache_error_does_not_fail(client, patch_helpers):
    """RedisError during cache write is swallowed — response still 200."""
    from redis.exceptions import RedisError
    ph = patch_helpers
    ph["execute"].return_value = [(3, "Carol", "Team Member", "Juniors")]
    ph["cache"].set.side_effect = RedisError("Redis down")

    resp = client.post("/api/auth/login", json={"user_name": "Carol"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_api_login_name_with_apostrophe(client, patch_helpers):
    """Names containing apostrophes must not be HTML-escaped before the DB query."""
    ph = patch_helpers
    ph["execute"].return_value = [(10, "O'Reilly", "Team Member", "Minis")]

    resp = client.post("/api/auth/login", json={"user_name": "O'Reilly"})
    assert resp.status_code == 200

    call_args = ph["execute"].call_args
    params = call_args[0][1]
    assert params["user_name"] == "O'Reilly"


def test_api_login_missing_user_name(client, patch_helpers):
    """POST body without user_name → 400."""
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 400
    assert "user_name required" in resp.get_json()["error"]


def test_api_login_invalid_user(client, patch_helpers):
    """user_name not found in DB → 401."""
    ph = patch_helpers
    ph["execute"].return_value = []

    resp = client.post("/api/auth/login", json={"user_name": "Ghost"})
    assert resp.status_code == 401
    assert "Invalid user" in resp.get_json()["error"]


def test_api_login_db_error(client, patch_helpers):
    """DB error during login → 500."""
    ph = patch_helpers
    ph["execute"].side_effect = SQLAlchemyError("db down")

    resp = client.post("/api/auth/login", json={"user_name": "Alice"})
    assert resp.status_code == 500
    assert "internal error" in resp.get_json()["error"].lower()


def test_api_login_non_leader_role(client, patch_helpers):
    """Team Member role results in is_leader=False."""
    ph = patch_helpers
    ph["execute"].return_value = [(4, "Dave", "Team Member", "Minis")]

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
    """Logout deletes the user's cache entry."""
    ph = patch_helpers
    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    client.post("/api/auth/logout")
    ph["cache"].delete.assert_called_once_with("user:data:Alice")


def test_api_logout_cache_error_does_not_fail(client, patch_helpers):
    """RedisError during cache delete is swallowed — response still 200."""
    from redis.exceptions import RedisError
    ph = patch_helpers
    ph["cache"].delete.side_effect = RedisError("Redis down")

    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_api_logout_without_session(client, patch_helpers):
    """Logout with no active session → still 200, cache.delete not called."""
    ph = patch_helpers

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    ph["cache"].delete.assert_not_called()