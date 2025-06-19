# backend/tests/test_users_routes.py
# Updated tests for new cache integration where utils functions handle caching

import pytest
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
    ph["by_section"].side_effect = Exception("DB error")

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
    resp = client.get("/user-duty")  # Missing user parameter
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "Missing parameters" in data["error"]

def test_user_duty_exception(client, patch_helpers):
    """Test exception handling in route"""
    ph = patch_helpers
    ph["duty"].side_effect = Exception("Oops")

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
    ph["execute"].side_effect = Exception("DB connection failed")

    resp = client.post("/select-user", json={"user_name": "Alice"})
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

def test_select_user_cache_error_handling(client, patch_helpers):
    """Test that cache errors don't break user selection"""
    ph = patch_helpers
    ph["execute"].return_value = [(42, "Alice", "Section Leader", "Minors")]
    # Make cache.set fail
    ph["cache"].set.side_effect = Exception("Cache failed")

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
    ph["cache"].get.side_effect = Exception("Cache failed")
    
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
    ph["all_users"].side_effect = Exception("Database error")

    resp = client.get("/get-users")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

# ─── 8) POST /logout ─────────────────────────────────────────────────────────────
def test_logout(client, patch_helpers):
    ph = patch_helpers
    
    with client.session_transaction() as sess:
        sess["user_name"] = "Someone"
    
    resp = client.post("/logout")
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
    """Test that cache errors don't break logout"""
    ph = patch_helpers
    ph["cache"].delete.side_effect = Exception("Cache failed")
    
    with client.session_transaction() as sess:
        sess["user_name"] = "Someone"
    
    resp = client.post("/logout")
    # Should still succeed even if cache clearing fails
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "User logged out successfully!"}

def test_logout_no_user(client, patch_helpers):
    ph = patch_helpers
    
    resp = client.post("/logout")
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
    ph["cache"].set.side_effect = Exception("Redis connection failed")

    resp = client.get("/cache-stats")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["cache_status"] == "unhealthy"

# ─── 10) NEW: Admin endpoints ────────────────────────────────────────────────────
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
    ph["clear_cache"].side_effect = Exception("Cache clear failed")
    
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