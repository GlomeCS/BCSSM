import os
import pytest
from unittest.mock import MagicMock, patch

from backend.bcssm_backend.utils import _fmt_ttl, _redact_redis_url
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
    monkeypatch.setattr("backend.bcssm_backend.utils.cache", fake)
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
