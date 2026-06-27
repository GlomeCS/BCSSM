import os
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend.health import _fmt_ttl, _redact_redis_url
from backend.bcssm_backend import create_app


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for var in ("user", "password", "host", "port", "database"):
        monkeypatch.setenv(var, "test")
    monkeypatch.setenv("FLASK_ENV", "testing")


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_cache(monkeypatch):
    fake = MagicMock()
    fake.get.return_value = None
    fake.set.return_value = True
    fake.delete.return_value = True
    fake.clear.return_value = True
    monkeypatch.setattr("backend.globals.cache", fake)
    monkeypatch.setattr("backend.bcssm_backend.health.cache", fake)
    return fake


# ─── _fmt_ttl: singular / plural ─────────────────────────────────────────────

@pytest.mark.parametrize("ttl,expected", [
    (1, "1 second"),
    (30, "30 seconds"),
    (59, "59 seconds"),
    (60, "1 minute"),
    (61, "1 minute"),      # 61 // 60 == 1
    (120, "2 minutes"),
    (3599, "59 minutes"),
    (3600, "1 hour"),
    (3601, "1 hour"),      # 3601 // 3600 == 1
    (7200, "2 hours"),
])
def test_fmt_ttl(ttl, expected):
    assert _fmt_ttl(ttl) == expected


# ─── _redact_redis_url: credentials stripped ─────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("redis://localhost:6379", "localhost:6379"),
    ("redis://redis:6379", "redis:6379"),
    ("redis://user:secret@redis.example.com:6379", "redis.example.com:6379"),
    ("redis://:password@10.0.0.1:6380", "10.0.0.1:6380"),
])
def test_redact_redis_url_admin(url, expected):
    assert _redact_redis_url(url) == expected


def test_redact_redis_url_system(url="redis://user:secret@host:6379"):
    assert _redact_redis_url(url) == "host:6379"


# ─── /api/admin/cache/status: URL is redacted ────────────────────────────────

def test_cache_status_does_not_expose_credentials(client, mock_cache, monkeypatch):
    mock_cache.get.return_value = "working"
    monkeypatch.setenv("REDIS_URL", "redis://svcacct:s3cret99@redis.prod.internal:6379")

    resp = client.get("/api/admin/cache/status")
    assert resp.status_code == 200
    data = resp.get_json()
    body = str(data)
    assert "s3cret99" not in body
    assert "svcacct" not in body
    assert "redis_url" in data
    assert data["redis_url"] == "redis.prod.internal:6379"


# ─── /api/admin/cache/info: URL is redacted ──────────────────────────────────

def test_cache_info_does_not_expose_credentials(client, monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://svcacct:xpassword99@cache.host:6379")

    resp = client.get("/api/admin/cache/info")
    assert resp.status_code == 200
    data = resp.get_json()
    body = str(data)
    assert "xpassword99" not in body
    assert "svcacct" not in body
    assert data["cache_config"]["url"] == "cache.host:6379"


# ─── /api/health: URL is redacted ────────────────────────────────────────────

def test_health_does_not_expose_credentials(client, mock_cache, monkeypatch):
    mock_cache.get.return_value = "ok"
    monkeypatch.setenv("REDIS_URL", "redis://ops:topsecret99@redis-prod:6379")

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    body = str(data)
    assert "topsecret99" not in body
    assert data["redis_url"] == "redis-prod:6379"


# ─── Path traversal: commonpath guard ────────────────────────────────────────

def test_path_traversal_sibling_folder_blocked(app, client, tmp_path, monkeypatch):
    # Set up a real static folder and a sibling that must not be accessible.
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><html></html>")

    sibling_dir = tmp_path / "static_backup"
    sibling_dir.mkdir()
    secret = sibling_dir / "secret.txt"
    secret.write_text("TOP SECRET")

    monkeypatch.setattr(app, "static_folder", str(static_dir))

    with app.test_client() as c:
        # A path that resolves outside static_dir via the sibling
        resp = c.get("/../static_backup/secret.txt")
        # Must serve index.html, not the secret file
        assert resp.status_code == 200
        assert b"TOP SECRET" not in resp.data


def test_path_traversal_dot_dot_blocked(app, tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><html></html>")

    parent_secret = tmp_path / "credentials.txt"
    parent_secret.write_text("SENSITIVE")

    monkeypatch.setattr(app, "static_folder", str(static_dir))

    with app.test_client() as c:
        resp = c.get("/../../credentials.txt")
        assert resp.status_code == 200
        assert b"SENSITIVE" not in resp.data


# ─── /api/admin/cache/clear ──────────────────────────────────────────────────

@pytest.mark.parametrize("cache_type,fn_name,expected_message", [
    ("all",      "clear_all_cache",      "Cleared all caches"),
    ("users",    "clear_user_cache",     "Cleared user-related caches"),
    ("duties",   "clear_duty_cache",     "Cleared duty-related caches"),
    ("feedback", "clear_feedback_cache", "Cleared feedback caches"),
])
def test_cache_clear_success(client, monkeypatch, cache_type, fn_name, expected_message):
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    monkeypatch.setattr(f"backend.bcssm_backend.routes.admin.{fn_name}", lambda: True)
    resp = client.post(
        "/api/admin/cache/clear",
        json={"type": cache_type},
        headers={"X-Admin-Secret": "correct-secret"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["message"] == expected_message
    assert data["cache_type"] == cache_type


def test_cache_clear_failure_returns_500(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    monkeypatch.setattr("backend.bcssm_backend.routes.admin.clear_all_cache", lambda: False)
    resp = client.post(
        "/api/admin/cache/clear",
        json={"type": "all"},
        headers={"X-Admin-Secret": "correct-secret"},
    )
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["success"] is False
    assert "Failed to clear" in data["error"]


def test_cache_clear_invalid_type_returns_400(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    resp = client.post(
        "/api/admin/cache/clear",
        json={"type": "invalid"},
        headers={"X-Admin-Secret": "correct-secret"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_cache_clear_unauthenticated_returns_403(client, monkeypatch):
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    resp = client.post("/api/admin/cache/clear", json={"type": "all"})
    assert resp.status_code == 403


# ─── _is_authorized_admin: session fast path ─────────────────────────────────

def test_passwords_status_session_admin_fast_path(client, monkeypatch):
    """Session with user_role='Admin' grants access without DB lookup or secret."""
    fake_status = [{"name": "Alice", "has_password": True}]
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.admin.get_all_users_password_status",
        lambda: fake_status,
    )
    with client.session_transaction() as sess:
        sess["user_role"] = "Admin"

    resp = client.get("/api/admin/passwords-status")
    assert resp.status_code == 200
    assert resp.get_json()["users"] == fake_status


def test_passwords_status_hmac_with_non_admin_session_grants_access(client, monkeypatch):
    """Session without Admin role falls through to HMAC check; correct secret grants access."""
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.admin.get_all_users_password_status",
        lambda: [],
    )

    resp = client.get(
        "/api/admin/passwords-status",
        headers={"X-Admin-Secret": "correct-secret"},
    )
    assert resp.status_code == 200


def test_passwords_status_no_admin_secret_env_returns_403(client, monkeypatch):
    """No ADMIN_SECRET env var → 403 even with a header."""
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    resp = client.get(
        "/api/admin/passwords-status",
        headers={"X-Admin-Secret": "anything"},
    )
    assert resp.status_code == 403


def test_passwords_status_no_header_returns_403(client, monkeypatch):
    """ADMIN_SECRET set but no X-Admin-Secret header → 403."""
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    resp = client.get("/api/admin/passwords-status")
    assert resp.status_code == 403


def test_passwords_status_wrong_header_returns_403(client, monkeypatch):
    """Wrong X-Admin-Secret value → 403."""
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    resp = client.get(
        "/api/admin/passwords-status",
        headers={"X-Admin-Secret": "wrong-secret"},
    )
    assert resp.status_code == 403


def test_passwords_status_correct_header_returns_200(client, monkeypatch):
    """Correct X-Admin-Secret → 200 with users list."""
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    fake_users = [{"name": "Alice", "has_password": True}]
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.admin.get_all_users_password_status",
        lambda: fake_users,
    )
    resp = client.get(
        "/api/admin/passwords-status",
        headers={"X-Admin-Secret": "correct-secret"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["users"] == fake_users


def test_passwords_status_db_error_returns_500(client, monkeypatch):
    """SQLAlchemyError from get_all_users_password_status → 500."""
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")

    def raise_db_error():
        raise SQLAlchemyError("db down")

    monkeypatch.setattr(
        "backend.bcssm_backend.routes.admin.get_all_users_password_status",
        raise_db_error,
    )
    resp = client.get(
        "/api/admin/passwords-status",
        headers={"X-Admin-Secret": "correct-secret"},
    )
    assert resp.status_code == 500


# ─── /api/admin/set-password ─────────────────────────────────────────────────

def _auth_headers(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
    return {"X-Admin-Secret": "correct-secret"}


def test_set_password_unauthorized_returns_403(client, monkeypatch):
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    resp = client.post(
        "/api/admin/set-password",
        json={"user_name": "Alice", "password": "validpassword"},
    )
    assert resp.status_code == 403


def test_set_password_missing_user_name_returns_400(client, monkeypatch):
    headers = _auth_headers(monkeypatch)
    resp = client.post(
        "/api/admin/set-password",
        json={"password": "validpassword"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "user_name" in resp.get_json()["error"]


def test_set_password_missing_password_returns_400(client, monkeypatch):
    headers = _auth_headers(monkeypatch)
    resp = client.post(
        "/api/admin/set-password",
        json={"user_name": "Alice"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_set_password_too_short_returns_400(client, monkeypatch):
    headers = _auth_headers(monkeypatch)
    resp = client.post(
        "/api/admin/set-password",
        json={"user_name": "Alice", "password": "short"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "8 characters" in resp.get_json()["error"]


def test_set_password_user_not_found_returns_404(client, monkeypatch):
    headers = _auth_headers(monkeypatch)
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.admin.set_user_password",
        lambda user_name, password_hash: False,
    )
    with patch("backend.bcssm_backend.routes.admin.bcrypt.hashpw", return_value=b"$2b$12$fakehash"):
        with patch("backend.bcssm_backend.routes.admin.bcrypt.gensalt", return_value=b"$2b$12$"):
            resp = client.post(
                "/api/admin/set-password",
                json={"user_name": "Ghost", "password": "validpassword"},
                headers=headers,
            )
    assert resp.status_code == 404


def test_set_password_success_returns_200(client, monkeypatch):
    headers = _auth_headers(monkeypatch)
    monkeypatch.setattr(
        "backend.bcssm_backend.routes.admin.set_user_password",
        lambda user_name, password_hash: True,
    )
    with patch("backend.bcssm_backend.routes.admin.bcrypt.hashpw", return_value=b"$2b$12$fakehash"):
        with patch("backend.bcssm_backend.routes.admin.bcrypt.gensalt", return_value=b"$2b$12$"):
            resp = client.post(
                "/api/admin/set-password",
                json={"user_name": "Alice", "password": "validpassword"},
                headers=headers,
            )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["user_name"] == "Alice"


def test_set_password_db_error_returns_500(client, monkeypatch):
    headers = _auth_headers(monkeypatch)

    def raise_db_error(user_name, password_hash):
        raise SQLAlchemyError("db down")

    monkeypatch.setattr(
        "backend.bcssm_backend.routes.admin.set_user_password",
        raise_db_error,
    )
    with patch("backend.bcssm_backend.routes.admin.bcrypt.hashpw", return_value=b"$2b$12$fakehash"):
        with patch("backend.bcssm_backend.routes.admin.bcrypt.gensalt", return_value=b"$2b$12$"):
            resp = client.post(
                "/api/admin/set-password",
                json={"user_name": "Alice", "password": "validpassword"},
                headers=headers,
            )
    assert resp.status_code == 500
