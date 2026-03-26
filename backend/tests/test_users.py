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
    """Test user duty - now uses utils function with built-in caching"""
    ph = patch_helpers
    # Mock utils function returns data directly (already cached internally)
    ph["duty"].return_value = {"user": "Alice", "duty": "Cleaning"}

    resp = client.get("/user-duty?user=Alice")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": "Alice", "duty": "Cleaning"}
    
    # Verify utils function was called (caching happens inside utils)
    ph["duty"].assert_called_once_with("Alice")
    # Route-level cache operations no longer happen
    assert not ph["cache"].get.called
    assert not ph["cache"].set.called

def test_user_duty_error_response(client, patch_helpers):
    """Test user duty when utils returns error dict"""
    ph = patch_helpers
    # Mock utils function returns error (as per utils.py implementation)
    ph["duty"].return_value = {"error": "User not found or no duty assigned"}

    resp = client.get("/user-duty?user=Alice")
    assert resp.status_code == 200  # Route returns the error data, doesn't fail
    data = resp.get_json()
    assert "error" in data
    assert "User not found or no duty assigned" in data["error"]
    
def test_user_duty_missing_param(client, patch_helpers):
    """Test /user-duty without username parameter - updated for new route behavior"""
    resp = client.get("/user-duty")  # Missing user parameter
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    # Updated assertion - the route now uses get_username_from_request() which returns "Username required"
    assert "Username required" in data["error"]

def test_user_duty_exception(client, patch_helpers):
    """Test exception handling in route"""
    ph = patch_helpers
    ph["duty"].side_effect = SQLAlchemyError("Oops")

    resp = client.get("/user-duty?user=Alice")
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
def test_validate_user_success_with_query_param(client, patch_helpers):
    """Test /api/auth/validate with valid user via query parameter"""
    ph = patch_helpers
    # Mock successful user lookup
    ph["execute"].return_value = [(42, "Alice", "Section Leader", "Minors")]

    resp = client.get("/api/auth/validate?user_name=Alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_valid"] is True
    assert data["user_name"] == "Alice"
    assert data["role"] == "Section Leader"
    assert data["section"] == "Minors"
    assert data["is_leader"] is True

def test_validate_user_success_with_header(client, patch_helpers):
    """Test /api/auth/validate with valid user via header"""
    ph = patch_helpers
    # Mock successful user lookup
    ph["execute"].return_value = [(43, "Bob", "Team Member", "Majors")]

    resp = client.get("/api/auth/validate", headers={"X-Current-User": "Bob"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_valid"] is True
    assert data["user_name"] == "Bob"
    assert data["role"] == "Team Member"
    assert data["section"] == "Majors"
    assert data["is_leader"] is False

def test_validate_user_success_with_session(client, patch_helpers):
    """Test /api/auth/validate with valid user via session"""
    ph = patch_helpers
    # Mock successful user lookup
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
    assert data["is_leader"] is True  # Admin counts as leader

def test_validate_user_team_leader_role(client, patch_helpers):
    """Test /api/auth/validate correctly identifies team leader as leader"""
    ph = patch_helpers
    # Mock team leader user
    ph["execute"].return_value = [(45, "David", "Team Leader", "Micros")]

    resp = client.get("/api/auth/validate?user_name=David")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_valid"] is True
    assert data["user_name"] == "David"
    assert data["role"] == "Team Leader"
    assert data["section"] == "Micros"
    assert data["is_leader"] is True  # Team Leader counts as leader

def test_validate_user_no_username_provided(client, patch_helpers):
    """Test /api/auth/validate without any username"""
    resp = client.get("/api/auth/validate")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["is_valid"] is False
    assert "No username provided" in data["error"]

def test_validate_user_invalid_user(client, patch_helpers):
    """Test /api/auth/validate with user not found in database"""
    ph = patch_helpers
    # Mock user not found
    ph["execute"].return_value = []

    resp = client.get("/api/auth/validate?user_name=NonExistentUser")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["is_valid"] is False
    assert "Invalid user" in data["error"]

def test_validate_user_database_error(client, patch_helpers):
    """Test /api/auth/validate with database error"""
    ph = patch_helpers
    # Mock database error
    ph["execute"].side_effect = SQLAlchemyError("Database connection failed")

    resp = client.get("/api/auth/validate?user_name=Alice")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["is_valid"] is False
    assert "Validation failed" in data["error"]

def test_validate_user_user_without_section(client, patch_helpers):
    """Test /api/auth/validate with user that has no section"""
    ph = patch_helpers
    # Mock user without section (section_name is None)
    ph["execute"].return_value = [(46, "Eve", "Team Member", None)]

    resp = client.get("/api/auth/validate?user_name=Eve")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_valid"] is True
    assert data["user_name"] == "Eve"
    assert data["role"] == "Team Member"
    assert data["section"] is None
    assert data["is_leader"] is False

def test_validate_user_multiple_auth_sources_priority(client, patch_helpers):
    """Test /api/auth/validate prioritizes query param over other sources"""
    ph = patch_helpers
    # Mock successful user lookup
    ph["execute"].return_value = [(47, "QueryUser", "Section Leader", "Minis")]

    # Set up multiple potential username sources
    with client.session_transaction() as sess:
        sess["user_name"] = "SessionUser"

    # Query param should take priority
    resp = client.get("/api/auth/validate?user_name=QueryUser", 
                     headers={"X-Current-User": "HeaderUser"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user_name"] == "QueryUser"  # Should use query param, not header or session

def test_validate_user_execute_query_called_correctly(client, patch_helpers):
    """Test that execute_query is called with correct parameters"""
    ph = patch_helpers
    # Mock successful user lookup
    ph["execute"].return_value = [(48, "TestUser", "Team Member", "TestSection")]

    resp = client.get("/api/auth/validate?user_name=TestUser")
    assert resp.status_code == 200

    # Verify execute_query was called with correct SQL and parameters
    ph["execute"].assert_called_once()
    call_args = ph["execute"].call_args
    sql, params = call_args[0]
    
    # Check SQL structure
    assert "SELECT u.id, u.name, u.role, s.name AS section_name" in sql
    assert "FROM users u" in sql
    assert "LEFT JOIN sections s ON u.section_id = s.id" in sql
    assert "WHERE u.name = :user_name" in sql
    
    # Check parameters
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