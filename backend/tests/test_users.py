import pytest
from backend.bcssm_backend import create_app
from backend.bcssm_backend.routes.users import init_users_routes
from flask import session
from unittest.mock import MagicMock

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
    patch_helpers["by_section"].return_value = [{"name": "Alice", "role": "Leader"}]

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.get_json() == {"users": [{"name": "Alice", "role": "Leader"}]}
    patch_helpers["by_section"].assert_called_once_with("Minors")

def test_users_by_section_error(client, patch_helpers):
    patch_helpers["by_section"].side_effect = Exception("DB error")

    resp = client.get("/users-by-section?section=Minors")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

# ─── 4) GET /user-duty ────────────────────────────────────────────────────────────
def test_user_duty_success(client, patch_helpers):
    patch_helpers["duty"].return_value = {"user": "Alice", "duty": "Cleaning"}

    resp = client.get("/user-duty?user=Alice")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": "Alice", "duty": "Cleaning"}
    patch_helpers["duty"].assert_called_once_with("Alice")

def test_user_duty_error(client, patch_helpers):
    patch_helpers["duty"].side_effect = Exception("Oops")

    resp = client.get("/user-duty?user=Alice")
    assert resp.status_code == 500
    data = resp.get_json()
    assert "error" in data

# ─── 5) POST /select-user ───────────────────────────────────────────────────────
def test_select_user_from_cache(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = ["Alice", "Bob"]
    ph["execute"].return_value = [(42, "Section Leader", "Minors")]

    resp = client.post("/select-user", json={"user_name": "Alice"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "User Alice successfully selected."
    # Should include full login state
    assert data["is_logged_in"] is True
    assert data["is_leader"] is True
    assert data["user_section"] == "Minors"
    # user_id is stored in session, not returned in JSON

    with client.session_transaction() as sess:
        assert sess["user_name"] == "Alice"
        assert sess["user_id"] == 42
        assert sess["user_section"] == "Minors"
        assert sess["is_leader"] is True

    ph["cache"].get.assert_called_once_with("valid_users")
    ph["execute"].assert_called_once()

def test_select_user_invalid(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = ["Alice", "Bob"]

    resp = client.post("/select-user", json={"user_name": "Charlie"})
    assert resp.status_code == 400
    assert resp.get_json() == {"message": "Invalid user selected."}

    with client.session_transaction() as sess:
        assert sess.get("user_name") is None

def test_select_user_loads_cache_when_empty(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = None
    ph["all_users"].return_value = ["Alice", "Bob"]
    ph["execute"].return_value = [(5, "Member", "Majors")]

    resp = client.post("/select-user", json={"user_name": "Bob"})
    assert resp.status_code == 200

    ph["cache"].get.assert_called_once_with("valid_users")
    ph["all_users"].assert_called_once()
    ph["cache"].set.assert_called_once_with("valid_users", ["Alice", "Bob"], timeout=300)

# ─── 6) GET /get-selected-user ───────────────────────────────────────────────────
def test_get_selected_user(client):
    with client.session_transaction() as sess:
        sess["user_name"] = "Zed"
    resp = client.get("/get-selected-user")
    assert resp.status_code == 200
    assert resp.get_json() == {"user": "Zed"}

def test_get_selected_user_none(client):
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
    ph["cache"].get.assert_called_once_with("all_users")
    ph["all_users"].assert_not_called()

def test_get_users_loads_when_cache_empty(client, patch_helpers):
    ph = patch_helpers
    ph["cache"].get.return_value = None
    ph["all_users"].return_value = ["X", "Y"]

    resp = client.get("/get-users")
    assert resp.status_code == 200
    assert resp.get_json() == {"users": ["X", "Y"]}
    ph["cache"].get.assert_called_once_with("all_users")
    ph["all_users"].assert_called_once()
    ph["cache"].set.assert_called_once_with("all_users", ["X", "Y"], timeout=300)

# ─── 8) POST /logout ─────────────────────────────────────────────────────────────
def test_logout(client, patch_helpers):
    with client.session_transaction() as sess:
        sess["user_name"] = "Someone"
    resp = client.post("/logout")
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "User logged out successfully!"}
    with client.session_transaction() as sess:
        assert sess.get("user_name") is None