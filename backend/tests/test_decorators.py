import logging
import pytest
from flask import jsonify
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend import create_app
from backend.bcssm_backend.decorators import handle_route_errors, require_auth
from backend.bcssm_backend.exceptions import (
    AuthenticationError, DatabaseError, NotFoundError, ValidationError
)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    return create_app()


def _make_route(app, exc=None, return_value=None):
    """Register a test route that either raises exc or returns return_value."""
    @app.route('/test-errors')
    @handle_route_errors
    def test_route():
        if exc is not None:
            raise exc
        return jsonify(return_value or {"ok": True}), 200


# ─── handle_route_errors ─────────────────────────────────────────────────────

def test_handle_route_errors_passes_through_success(app):
    _make_route(app, return_value={"result": "ok"})
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 200
    assert response.get_json() == {"result": "ok"}


def test_handle_route_errors_validation_error_returns_400(app):
    _make_route(app, exc=ValidationError("bad input"))
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 400
    assert response.get_json() == {"error": "bad input"}


def test_handle_route_errors_authentication_error_returns_401(app):
    _make_route(app, exc=AuthenticationError("not logged in"))
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 401
    assert response.get_json() == {"error": "not logged in"}


def test_handle_route_errors_not_found_error_returns_404(app):
    _make_route(app, exc=NotFoundError("resource missing"))
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 404
    assert response.get_json() == {"error": "resource missing"}


def test_handle_route_errors_database_error_returns_500(app):
    _make_route(app, exc=DatabaseError("db down"))
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_handle_route_errors_sqlalchemy_error_returns_500(app):
    _make_route(app, exc=SQLAlchemyError("connection refused"))
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_handle_route_errors_generic_exception_returns_500(app):
    _make_route(app, exc=RuntimeError("unexpected crash"))
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_handle_route_errors_logs_warning_for_validation_error(app, caplog):
    _make_route(app, exc=ValidationError("too short"))
    with app.test_client() as client:
        with caplog.at_level(logging.WARNING):
            client.get('/test-errors')
    assert "Validation error in test_route" in caplog.text
    assert "too short" in caplog.text


def test_handle_route_errors_logs_error_for_database_error(app, caplog):
    _make_route(app, exc=DatabaseError("query failed"))
    with app.test_client() as client:
        with caplog.at_level(logging.ERROR):
            client.get('/test-errors')
    assert "Database error in test_route" in caplog.text
    assert "query failed" in caplog.text


def test_handle_route_errors_logs_critical_for_unexpected(app, caplog):
    _make_route(app, exc=RuntimeError("explosion"))
    with app.test_client() as client:
        with caplog.at_level(logging.CRITICAL):
            client.get('/test-errors')
    assert "Unexpected error in test_route" in caplog.text
    assert "explosion" in caplog.text


def test_handle_route_errors_logs_error_for_sqlalchemy_error(app, caplog):
    _make_route(app, exc=SQLAlchemyError("timeout"))
    with app.test_client() as client:
        with caplog.at_level(logging.ERROR):
            client.get('/test-errors')
    assert "Database error in test_route" in caplog.text
    assert "timeout" in caplog.text


# ─── require_auth + handle_route_errors stacking ─────────────────────────────

def test_stacked_decorators_auth_checked_before_error_handler(app):
    """@require_auth rejects unauthenticated requests before error handler."""
    @app.route('/test-stacked')
    @require_auth
    @handle_route_errors
    def stacked_route():
        raise DatabaseError("should not reach here")

    with app.test_client() as client:
        response = client.get('/test-stacked')
    assert response.status_code == 401


def test_stacked_decorators_errors_caught_when_authenticated(app):
    """With valid session, @handle_route_errors catches exceptions."""
    @app.route('/test-stacked-auth')
    @require_auth
    @handle_route_errors
    def stacked_auth_route():
        raise ValidationError("field required")

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Alice'
        response = client.get('/test-stacked-auth')
    assert response.status_code == 400
    assert response.get_json() == {"error": "field required"}
