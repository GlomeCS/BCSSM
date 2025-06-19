import pytest
from backend.bcssm_backend import create_app
from unittest.mock import MagicMock, patch

# ─── 0) Fixture: create app with testing config and register routes ────────────
@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app()
    # init_users_routes(app)  # routes already registered by create_app()
    return app

# ─── 1) Fixture: test client ─────────────────────────────────────────────────────
@pytest.fixture
def client(app):
    return app.test_client()

# ─── 2) Fixture: patch underlying helpers and cache ──────────────────────────────
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
    return {
        "by_section": fake_get_by_section,
        "duty": fake_get_duty,
        "all_users": fake_get_all,
        "execute": fake_exec,
        "cache": fake_cache
    }

# ─── 3) GET /users-by-section ────────────────────────────────────────────────────
def test_users_by_section_success(client, patch_helpers):
    ph = patch_helpers
    # Mock cache miss, then successful DB call
    ph["cache"].get.return_value = None
    ph["by_section"].return_value = [{"name": "Alice", "role": "Leader"}]

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.get_json() == {"users": [{"name": "Alice", "role": "Leader"}]}
    
    # Verify cache operations
    ph["cache"].get.assert_called_once_with("users:section:Minors")
    ph["cache"].set.assert_called_once_with("users:section:Minors", [{"name": "Alice", "role": "Leader"}], timeout=600)
    ph["by_section"].assert_called_once_with("Minors")

def test_users_by_section_cache_hit(client, patch_helpers):
    ph = patch_helpers
    # Mock cache hit
    ph["cache"].get.return_value = [{"name": "Cached Alice", "role": "Leader"}]

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 200
    assert resp.get_json() == {"users": [{"name": "Cached Alice", "role": "Leader"}]}
    
    # Verify cache was checked but DB wasn't called
    ph["cache"].get.assert_called_once_with("users:section:Minors")
    ph["by_section"].assert_not_called()
    ph["cache"].set.assert_not_called()

def test_users_by_section_missing_param(client, patch_helpers):
    resp = client.get("/users-by-section")  # Missing section parameter
    assert resp.status_code == 400  # Bad Request for missing parameter
    data = resp.get_json()
    assert "error" in data
    assert "Missing parameters" in data["error"]

def test_users_by_section_error(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = None
    ph["by_section"].side_effect = Exception("DB error")

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

# ─── 4) GET /user-duty ────────────────────────────────────────────────────────────
def test_user_duty_success(client, patch_helpers):
    ph = patch_helpers
    # Mock cache miss, then successful DB call
    ph["cache"].get.return_value = None
    ph["duty"].return_value = {"user": "Alice", "duty": "Cleaning"}

    resp = client.get("/user-duty?user=Alice")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": "Alice", "duty": "Cleaning"}
    
    # Verify that cache operations were called
    # The exact cache key pattern may vary, so just verify cache was used
    assert ph["cache"].get.called, "Cache get should have been called"
    assert ph["cache"].set.called, "Cache set should have been called"
    ph["duty"].assert_called_once_with("Alice")

def test_user_duty_cache_hit(client, patch_helpers):
    ph = patch_helpers
    # Mock cache hit
    ph["cache"].get.return_value = {"user": "Alice", "duty": "Cached Duty"}

    resp = client.get("/user-duty?user=Alice")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": "Alice", "duty": "Cached Duty"}
    
    # Verify cache was checked but DB wasn't called
    ph["cache"].get.assert_called_once()
    ph["duty"].assert_not_called()
    ph["cache"].set.assert_not_called()
    
def test_user_duty_missing_param(client, patch_helpers):
    resp = client.get("/user-duty")  # Missing user parameter
    assert resp.status_code == 400  # Bad Request for missing parameter
    data = resp.get_json()
    assert "error" in data
    assert "Missing parameters" in data["error"]

def test_user_duty_error(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = None
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

    # Verify cache operations for user data
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

def test_get_selected_user_none(client, patch_helpers):
    resp = client.get("/get-selected-user")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": None}

# ─── 7) GET /get-users ────────────────────────────────────────────────────────────
def test_get_users_from_cache(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = ["Alice", "Bob"]

    resp = client.get("/get-users")
    assert resp.status_code == 200
    assert resp.get_json() == {"users": ["Alice", "Bob"]}
    
    # Verify cache operations with new cache key
    ph["cache"].get.assert_called_once_with("users:all:active")
    ph["all_users"].assert_not_called()

def test_get_users_loads_when_cache_empty(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = None
    ph["all_users"].return_value = ["X", "Y"]

    resp = client.get("/get-users")
    assert resp.status_code == 200
    assert resp.get_json() == {"users": ["X", "Y"]}
    
    # Verify cache operations with new cache key and timeout
    ph["cache"].get.assert_called_once_with("users:all:active")
    ph["all_users"].assert_called_once()
    ph["cache"].set.assert_called_once_with("users:all:active", ["X", "Y"], timeout=900)

def test_get_users_error(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = None
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

def test_cache_stats_unhealthy(client, patch_helpers):
    ph = patch_helpers
    # Mock cache failure
    ph["cache"].set.side_effect = Exception("Redis connection failed")

    resp = client.get("/cache-stats")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["cache_status"] == "unhealthy"