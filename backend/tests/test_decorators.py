import logging
import os
import pytest
from flask import jsonify, g
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend import create_app
from backend.bcssm_backend.decorators import (
    handle_route_errors, require_auth, require_role,
    require_feedback_edit_permission, require_admin,
)
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
        raise DatabaseError("should not reach here")  # pragma: no cover

    with app.test_client() as client:
        response = client.get('/test-stacked')
    assert response.status_code == 401


def test_handle_route_errors_http_exception_passes_through(app):
    """HTTPException (e.g. 404) must be re-raised, not swallowed as 500."""
    from werkzeug.exceptions import NotFound
    _make_route(app, exc=NotFound())
    with app.test_client() as client:
        response = client.get('/test-errors')
    assert response.status_code == 404


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
            sess['user_id'] = 1
            sess['user_role'] = 'Leader'
            sess['user_section'] = 'Minis'
        response = client.get('/test-stacked-auth')
    assert response.status_code == 400
    assert response.get_json() == {"error": "field required"}


def test_require_auth_user_id_db_lookup_returns_none_returns_401(app, monkeypatch):
    """Session has user_name + role/section but get_user_id_by_name returns None → 401."""
    monkeypatch.setattr(
        "backend.bcssm_backend.user_queries.get_user_id_by_name",
        lambda name: None,
    )

    @app.route('/test-require-auth-no-id')
    @require_auth
    def protected_route():
        return jsonify({"ok": True}), 200  # pragma: no cover

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Alice'
            sess['user_role'] = 'Leader'
            sess['user_section'] = 'Minis'
        response = client.get('/test-require-auth-no-id')
    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required"}



# ─── require_role ─────────────────────────────────────────────────────────────

def test_require_role_allowed_role_passes(app):
    """User with an allowed role gets through require_role."""
    @app.route('/test-require-role-pass')
    @require_auth
    @require_role("Admin", "Section Leader")
    def protected():
        return jsonify({"ok": True}), 200

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Alice'
            sess['user_id'] = 1
            sess['user_role'] = 'Admin'
            sess['user_section'] = 'Minis'
        response = client.get('/test-require-role-pass')
    assert response.status_code == 200


def test_require_role_disallowed_role_returns_403(app):
    """User without an allowed role is rejected by require_role."""
    @app.route('/test-require-role-block')
    @require_auth
    @require_role("Admin", "Section Leader")
    def protected():
        return jsonify({"ok": True}), 200  # pragma: no cover

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Bob'
            sess['user_id'] = 2
            sess['user_role'] = 'Leader'
            sess['user_section'] = 'Minis'
        response = client.get('/test-require-role-block')
    assert response.status_code == 403
    assert response.get_json() == {"error": "Forbidden"}


# ─── require_feedback_edit_permission ─────────────────────────────────────────

def test_require_feedback_edit_elevated_role_any_section_passes(app):
    """Elevated role (Section Leader) can edit any section."""
    @app.route('/test-feedback-edit')
    @require_auth
    @require_feedback_edit_permission
    def protected():
        return jsonify({"ok": True}), 200

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Alice'
            sess['user_id'] = 1
            sess['user_role'] = 'Section Leader'
            sess['user_section'] = 'Minis'
        response = client.get('/test-feedback-edit?section=Majors')
    assert response.status_code == 200


def test_require_feedback_edit_matching_section_passes(app):
    """Non-elevated role can edit their own section."""
    @app.route('/test-feedback-edit-own')
    @require_auth
    @require_feedback_edit_permission
    def protected():
        return jsonify({"ok": True}), 200

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Bob'
            sess['user_id'] = 2
            sess['user_role'] = 'Leader'
            sess['user_section'] = 'Minis'
        response = client.get('/test-feedback-edit-own?section=Minis')
    assert response.status_code == 200


def test_require_feedback_edit_wrong_role_wrong_section_returns_403(app):
    """Non-elevated role trying to edit a different section is rejected."""
    @app.route('/test-feedback-edit-forbidden')
    @require_auth
    @require_feedback_edit_permission
    def protected():
        return jsonify({"ok": True}), 200  # pragma: no cover

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Bob'
            sess['user_id'] = 2
            sess['user_role'] = 'Leader'
            sess['user_section'] = 'Minis'
        response = client.get('/test-feedback-edit-forbidden?section=Majors')
    assert response.status_code == 403
    assert response.get_json() == {"error": "Forbidden"}


# ─── require_admin ─────────────────────────────────────────────────────────────

def test_require_admin_session_admin_role_passes(app):
    """Session with user_role=Admin grants access."""
    @app.route('/test-admin-session')
    @require_admin
    def protected():
        return jsonify({"ok": True}), 200

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_role'] = 'Admin'
        response = client.get('/test-admin-session')
    assert response.status_code == 200


def test_require_admin_valid_hmac_passes(app, monkeypatch):
    """Valid X-Admin-Secret HMAC header grants access."""
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")

    @app.route('/test-admin-hmac')
    @require_admin
    def protected():
        return jsonify({"ok": True}), 200

    with app.test_client() as client:
        response = client.get('/test-admin-hmac', headers={"X-Admin-Secret": "correct-secret"})
    assert response.status_code == 200


def test_require_admin_neither_session_nor_hmac_returns_403(app, monkeypatch):
    """Neither Admin session nor valid HMAC → 403."""
    monkeypatch.delenv("ADMIN_SECRET", raising=False)

    @app.route('/test-admin-blocked')
    @require_admin
    def protected():
        return jsonify({"ok": True}), 200  # pragma: no cover

    with app.test_client() as client:
        response = client.get('/test-admin-blocked')
    assert response.status_code == 403
    assert response.get_json() == {"error": "Unauthorized"}


def test_require_admin_wrong_hmac_returns_403(app, monkeypatch):
    """Wrong X-Admin-Secret value → 403."""
    monkeypatch.setenv("ADMIN_SECRET", "correct-secret")

    @app.route('/test-admin-wrong-hmac')
    @require_admin
    def protected():
        return jsonify({"ok": True}), 200  # pragma: no cover

    with app.test_client() as client:
        response = client.get('/test-admin-wrong-hmac', headers={"X-Admin-Secret": "wrong"})
    assert response.status_code == 403


def test_require_admin_non_admin_session_role_returns_403(app, monkeypatch):
    """Session with user_role != Admin is rejected without a valid HMAC."""
    monkeypatch.delenv("ADMIN_SECRET", raising=False)

    @app.route('/test-admin-non-admin-role')
    @require_admin
    def protected():
        return jsonify({"ok": True}), 200  # pragma: no cover

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_role'] = 'Leader'
        response = client.get('/test-admin-non-admin-role')
    assert response.status_code == 403
