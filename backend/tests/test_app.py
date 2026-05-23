# Updated test_app.py with new cache management tests

import logging
import os
from unittest.mock import MagicMock, patch
import json

import pytest
from flask import Flask
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend import configure_logging, create_app
from backend.bcssm_backend.exceptions import (
    BaseError, DatabaseError, CacheError, ValidationError,
    AuthenticationError, NotFoundError,
)
from backend.bcssm_backend.routes.admin import _fmt_ttl


@pytest.fixture(scope="function")
def clean_env():
    """Fixture to clean and restore environment variables after each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_db_cache():
    """Fixture to mock database and cache."""
    fake_cache = MagicMock()
    fake_cache.init_app = MagicMock()
    fake_cache.set = MagicMock(return_value=True)
    fake_cache.get = MagicMock()
    fake_cache.delete = MagicMock(return_value=True)
    fake_cache.clear = MagicMock(return_value=True)
    fake_cache.cached = lambda *args, **kwargs: (lambda f: f)

    with patch('backend.bcssm_backend.db') as mock_db, \
         patch('backend.bcssm_backend.cache', fake_cache), \
         patch('backend.bcssm_backend.routes.admin.cache', fake_cache), \
         patch('backend.bcssm_backend.routes.system.cache', fake_cache):
        mock_db.init_app = MagicMock()
        yield mock_db, fake_cache


def test_create_app_with_valid_env_vars(clean_env, mock_db_cache):
    """Test that create_app initializes correctly with valid environment variables."""
    os.environ['FLASK_ENV'] = 'testing'  # ✅ Ensure it's in testing mode
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    mock_db, _mock_cache = mock_db_cache
    app = create_app()

    assert isinstance(app, Flask)
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'postgresql://test_user:test_password@localhost:6543/test_db'
    assert app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] is False

    # ✅ Only check init_app if NOT in testing mode
    if not app.config.get("TESTING"):
        mock_db.init_app.assert_called_once_with(app)
    else:
        mock_db.init_app.assert_not_called()  # ✅ Ensure it's not called in testing mode


@patch.dict(os.environ, {}, clear=True)
@patch('backend.bcssm_backend.load_dotenv')
def test_create_app_missing_env_vars_raises_error(mock_load_dotenv):
    """Test that create_app raises an error when required env vars are missing."""
    mock_load_dotenv.return_value = None

    with pytest.raises(RuntimeError, match="Missing required database environment variables."):
        create_app()


@patch('logging.basicConfig')
@patch('logging.getLogger')
def test_configure_logging(mock_get_logger, mock_basic_config):
    """Test that logging is configured correctly."""
    app = MagicMock()
    app.logger.setLevel = MagicMock()

    configure_logging(app)

    mock_basic_config.assert_called_once_with(
        level=logging.DEBUG,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )
    app.logger.setLevel.assert_called_once_with(logging.DEBUG)

@pytest.mark.parametrize("env, expected_env, expected_debug", [
    ("production", "production", False),  # Production case
    ("unknown_env", "development", True),  # Fallback to development
])
def test_create_app_config(clean_env, mock_db_cache, monkeypatch, env, expected_env, expected_debug):
    """Test that create_app() applies the correct config based on FLASK_ENV."""
    monkeypatch.setenv("FLASK_ENV", env)  # Mock FLASK_ENV
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_password")
    monkeypatch.setenv("host", "localhost")
    monkeypatch.setenv("database", "test_db")

    mock_db, mock_cache = mock_db_cache  # Use mocked db and cache

    app = create_app()

    expected_db_uri = f"postgresql://test_user:test_password@localhost:6543/test_db"

    assert app.config["ENV"] == expected_env  # Check the environment variable was applied
    assert app.config["DEBUG"] == expected_debug  # Check DEBUG mode
    assert app.config["SQLALCHEMY_DATABASE_URI"] == expected_db_uri  # Ensure correct DB URI
    assert isinstance(app.config, dict)  # Ensure app config is loaded correctly

    mock_db.init_app.assert_called_once_with(app)
    mock_cache.init_app.assert_called_once_with(app)

# Test that /api/sections returns data (removed caching decorator since it's internal now)
@patch('backend.bcssm_backend.routes.system.get_all_sections')
def test_api_sections_returns_data(mock_get_all_sections, mock_db_cache, clean_env):
    """Test /api/sections endpoint returns data from get_all_sections"""
    mock_get_all_sections.return_value = [{"id": "123", "name": "Minors"}, {"id": "456", "name": "Majors"}]

    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.get("/api/sections")
    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == [{"id": "123", "name": "Minors"}, {"id": "456", "name": "Majors"}]
    mock_get_all_sections.assert_called_once()

# NEW: Test the health check endpoint
def test_health_check_endpoint_healthy(mock_db_cache, clean_env):
    """Test /api/health endpoint when cache is healthy"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'
    os.environ['REDIS_URL'] = 'redis://localhost:6379'

    _mock_db, mock_cache = mock_db_cache
    # Configure mock to return 'ok' for health check
    mock_cache.get.return_value = 'ok'

    app = create_app()
    client = app.test_client()

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["cache"] == "healthy"
    assert data["environment"] == "testing"
    assert "redis_url" in data

def test_health_check_endpoint_cache_unhealthy(mock_db_cache, clean_env):
    """Test /api/health endpoint when cache is unhealthy"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, mock_cache = mock_db_cache
    # Make cache.get return wrong value to simulate unhealthy cache
    mock_cache.get.return_value = 'not_ok'

    app = create_app()
    client = app.test_client()

    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "degraded"  # Should be degraded when cache fails
    assert data["cache"] == "unhealthy"

def test_health_check_endpoint_exception(mock_db_cache, clean_env):
    """Test /api/health endpoint when cache throws exception"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, mock_cache = mock_db_cache
    # Make cache operations throw exception
    mock_cache.set.side_effect = RedisError("Redis connection failed")

    app = create_app()
    client = app.test_client()

    response = client.get("/api/health")
    assert response.status_code == 500

    data = response.get_json()
    assert data["status"] == "unhealthy"
    assert "Health check failed" in data["error"]

# NEW: Test cache management endpoints
@patch('backend.bcssm_backend.routes.admin.clear_user_cache')
def test_clear_cache_users(mock_clear_user_cache, mock_db_cache, clean_env):
    """Test POST /api/admin/cache/clear with type=users"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.post('/api/admin/cache/clear',
                          json={'type': 'users'},
                          content_type='application/json')

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "user" in data["message"].lower()
    assert data["cache_type"] == "users"

    mock_clear_user_cache.assert_called_once()

@patch('backend.bcssm_backend.routes.admin.clear_duty_cache')
def test_clear_cache_duties(mock_clear_duty_cache, mock_db_cache, clean_env):
    """Test POST /api/admin/cache/clear with type=duties"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.post('/api/admin/cache/clear',
                          json={'type': 'duties'},
                          content_type='application/json')

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "duty" in data["message"].lower()

    mock_clear_duty_cache.assert_called_once()

@patch('backend.bcssm_backend.routes.admin.clear_feedback_cache')
def test_clear_cache_feedback(mock_clear_feedback_cache, mock_db_cache, clean_env):
    """Test POST /api/admin/cache/clear with type=feedback"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.post('/api/admin/cache/clear',
                          json={'type': 'feedback'},
                          content_type='application/json')

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    mock_clear_feedback_cache.assert_called_once()

@patch('backend.bcssm_backend.routes.admin.clear_all_cache')
def test_clear_cache_all(mock_clear_all_cache, mock_db_cache, clean_env):
    """Test POST /api/admin/cache/clear with type=all"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.post('/api/admin/cache/clear',
                          json={'type': 'all'},
                          content_type='application/json')

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    mock_clear_all_cache.assert_called_once()

def test_clear_cache_invalid_type(mock_db_cache, clean_env):
    """Test POST /api/admin/cache/clear with invalid type"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.post('/api/admin/cache/clear',
                          json={'type': 'invalid'},
                          content_type='application/json')

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Invalid cache type" in data["error"]

def test_clear_cache_no_json(mock_db_cache, clean_env):
    """Test POST /api/admin/cache/clear without JSON defaults to all"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    with patch('backend.bcssm_backend.routes.admin.clear_all_cache') as mock_clear_all:
        response = client.post('/api/admin/cache/clear')

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["cache_type"] == "all"

        mock_clear_all.assert_called_once()

@patch('backend.bcssm_backend.routes.admin.clear_user_cache')
def test_clear_cache_exception_handling(mock_clear_user_cache, mock_db_cache, clean_env):
    """Test cache clear endpoint handles exceptions properly"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    mock_clear_user_cache.side_effect = RedisError("Cache clearing failed")

    app = create_app()
    client = app.test_client()

    response = client.post('/api/admin/cache/clear',
                          json={'type': 'users'},
                          content_type='application/json')

    assert response.status_code == 500
    data = response.get_json()
    assert data["success"] is False
    assert "Cache clearing failed" in data["error"]

def test_cache_status_endpoint(mock_db_cache, clean_env):
    """Test GET /api/admin/cache/status endpoint"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'
    os.environ['REDIS_URL'] = 'redis://localhost:6379'

    _mock_db, mock_cache = mock_db_cache

    # Ensure the mock returns the correct value for the status check
    mock_cache.get.return_value = 'working'  # This is what the status endpoint expects

    app = create_app()
    client = app.test_client()

    response = client.get('/api/admin/cache/status')

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["cache_type"] == "RedisCache"
    assert data["default_timeout"] == 300
    assert "available_operations" in data
    assert data["redis_url"] == "redis://localhost:6379"

    # Verify the cache was tested properly
    mock_cache.set.assert_called_with('status_test', 'working', timeout=10)
    mock_cache.get.assert_called_with('status_test')
    mock_cache.delete.assert_called_with('status_test')

def test_cache_status_endpoint_exception(mock_db_cache, clean_env):
    """Test cache status endpoint when cache throws exception"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, mock_cache = mock_db_cache
    mock_cache.set.side_effect = RedisError("Redis down")

    app = create_app()
    client = app.test_client()

    response = client.get('/api/admin/cache/status')

    assert response.status_code == 500
    data = response.get_json()
    assert data["status"] == "unhealthy"
    assert "Cache status check failed" in data["error"]

def test_cache_info_endpoint(mock_db_cache, clean_env):
    """Test GET /api/admin/cache/info endpoint"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.get('/api/admin/cache/info')

    assert response.status_code == 200
    data = response.get_json()
    assert "cache_config" in data
    assert "cached_functions" in data
    assert "management_endpoints" in data

    # Check specific function timeouts are documented
    assert "get_all_users" in data["cached_functions"]
    assert "15 minutes" in data["cached_functions"]["get_all_users"]

# Existing React serving tests (unchanged)
from unittest.mock import patch

@patch('backend.bcssm_backend.load_dotenv')
def test_serve_react_for_prefix_routes(mock_load_dotenv, monkeypatch, mock_db_cache, clean_env):
    """Test that routes starting with API or other prefixes are served via send_static_file."""
    # Set environment
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_password")
    monkeypatch.setenv("host", "localhost")
    monkeypatch.setenv("database", "test_db")
    # Initialize app
    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    # Patch send_static_file on the app instance
    app.send_static_file = MagicMock(return_value="served index.html via send_static_file")
    # Test each prefix
    for path in ["/api/foo", "/get-bar", "/select-baz", "/devos-xyz", "/duty-123"]:
        response = app.test_client().get(path)
        app.send_static_file.assert_called_with("index.html")
        assert response.get_data(as_text=True) == "served index.html via send_static_file"

@patch('backend.bcssm_backend.routes.system.send_from_directory')
@patch('backend.bcssm_backend.load_dotenv')
def test_directory_traversal_fallback(mock_load_dotenv, mock_send, monkeypatch, mock_db_cache, clean_env):
    """Test that directory traversal attempts fallback to index.html via send_from_directory."""
    # Set environment
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_password")
    monkeypatch.setenv("host", "localhost")
    monkeypatch.setenv("database", "test_db")
    # Simulate missing file and commonpath indicating traversal
    monkeypatch.setattr(os.path, "isfile", lambda path: False)
    # Initialize app
    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    # Configure mock return
    mock_send.return_value = "served index.html via send_from_directory"
    # Attempt traversal
    response = app.test_client().get("../etc/passwd")
    mock_send.assert_called_once_with(app.static_folder, "index.html")
    assert response.get_data(as_text=True) == "served index.html via send_from_directory"

@patch('backend.bcssm_backend.routes.system.send_from_directory')
@patch('backend.bcssm_backend.load_dotenv')
def test_serve_existing_static_file_branch(mock_load_dotenv, mock_send, monkeypatch, mock_db_cache, clean_env):
    """Test that existing static files are served via send_from_directory."""
    # Set environment
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_password")
    monkeypatch.setenv("host", "localhost")
    monkeypatch.setenv("database", "test_db")
    # Simulate file exists
    monkeypatch.setattr(os.path, "isfile", lambda path: True)
    # Initialize app
    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    # Configure mock return
    mock_send.return_value = "served main.css"
    # Request an existing file
    response = app.test_client().get("/main.css")
    mock_send.assert_called_once_with(app.static_folder, "main.css")
    assert response.get_data(as_text=True) == "served main.css"

def test_run_app_function(clean_env, mock_db_cache):
    """Test the extracted run_app function for 100% coverage"""
    os.environ['FLASK_ENV'] = 'development'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache

    with patch('backend.bcssm_backend.create_app') as mock_create_app:
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        # Import and call the extracted function
        from backend.bcssm_backend import run_app
        run_app()

        mock_create_app.assert_called_once()
        mock_app.run.assert_called_once_with(
            host="0.0.0.0",
            port=8080,
            debug=True
        )


# ─── Tests for custom exceptions module ──────────────────────────────────────

def test_base_error_defaults():
    e = BaseError("something went wrong")
    assert e.message == "something went wrong"
    assert e.status_code == 500
    assert str(e) == "something went wrong"


def test_base_error_custom_status():
    e = BaseError("custom", status_code=422)
    assert e.status_code == 422


def test_database_error_defaults():
    e = DatabaseError()
    assert e.status_code == 500
    assert "database" in e.message.lower()


def test_cache_error_defaults():
    e = CacheError()
    assert e.status_code == 500


def test_validation_error_defaults():
    e = ValidationError()
    assert e.status_code == 400


def test_authentication_error_defaults():
    e = AuthenticationError()
    assert e.status_code == 401


def test_not_found_error_defaults():
    e = NotFoundError()
    assert e.status_code == 404


def test_exceptions_are_base_error_subclasses():
    for cls in (DatabaseError, CacheError, ValidationError, AuthenticationError, NotFoundError):
        assert issubclass(cls, BaseError)
        assert issubclass(cls, Exception)


# ─── Tests for global Flask error handlers ───────────────────────────────────

@pytest.fixture
def error_handler_app(mock_db_cache, clean_env):
    """App fixture with a test route that can raise on demand."""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()

    # Register test-only routes to trigger specific exceptions
    @app.route('/test/base-error')
    def trigger_base_error():
        raise ValidationError("test validation failed")

    @app.route('/test/unhandled')
    def trigger_unhandled():
        raise RuntimeError("totally unexpected")

    @app.route('/test/db-error')
    def trigger_db_error():
        raise SQLAlchemyError("unhandled db error")

    @app.route('/test/http-exception')
    def trigger_http_exception():
        from flask import abort
        abort(403)  # No 403 handler registered → falls through to Exception handler

    return app


def test_global_handler_base_error(error_handler_app):
    client = error_handler_app.test_client()
    resp = client.get('/test/base-error')
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "test validation failed"


def test_global_handler_unhandled_exception(error_handler_app):
    client = error_handler_app.test_client()
    resp = client.get('/test/unhandled')
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["error"] == "Internal server error"


def test_global_handler_404_api_path(error_handler_app):
    client = error_handler_app.test_client()
    resp = client.get('/api/this-does-not-exist-at-all-xyz')
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "Resource not found"


def test_global_handler_405_method_not_allowed(error_handler_app):
    client = error_handler_app.test_client()
    # /api/health only allows GET — POST should get 405
    resp = client.post('/api/health')
    assert resp.status_code == 405
    data = resp.get_json()
    assert data["error"] == "Method not allowed"


def test_global_handler_db_error(error_handler_app):
    """Test handle_db_error catches unhandled SQLAlchemyError (covers lines 186-187)"""
    client = error_handler_app.test_client()
    resp = client.get('/test/db-error')
    assert resp.status_code == 500
    data = resp.get_json()
    assert data["error"] == "A database error occurred"


def test_global_handler_http_exception_passthrough(error_handler_app):
    """Test handle_exception passes HTTPException through unchanged (covers line 202)"""
    client = error_handler_app.test_client()
    resp = client.get('/test/http-exception')
    # 403 Forbidden — no specific 403 handler, goes to Exception handler,
    # isinstance check passes and the HTTPException is returned as-is
    assert resp.status_code == 403


@patch('backend.bcssm_backend.routes.system.get_all_sections')
def test_api_sections_error_dict_returns_500(mock_get_all_sections, mock_db_cache, clean_env):
    """Test /api/sections returns 500 when get_all_sections returns an error dict."""
    mock_get_all_sections.return_value = {"error": "DB unavailable"}

    os.environ['FLASK_ENV'] = 'testing'
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    _mock_db, _mock_cache = mock_db_cache
    app = create_app()
    client = app.test_client()

    response = client.get("/api/sections")
    assert response.status_code == 500
    data = response.get_json()
    assert data["error"] == "Failed to fetch sections"


# ─── _fmt_ttl unit tests ───────────────────────────────────────────────────────

def test_fmt_ttl_seconds():
    assert _fmt_ttl(30) == "30 seconds"
    assert _fmt_ttl(1) == "1 seconds"
    assert _fmt_ttl(59) == "59 seconds"


def test_fmt_ttl_minutes():
    assert _fmt_ttl(60) == "1 minutes"
    assert _fmt_ttl(120) == "2 minutes"
    assert _fmt_ttl(900) == "15 minutes"
    assert _fmt_ttl(3599) == "59 minutes"


def test_fmt_ttl_hours():
    assert _fmt_ttl(3600) == "1 hour"
    assert _fmt_ttl(7200) == "2 hours"
    assert _fmt_ttl(7800) == "2 hours"
