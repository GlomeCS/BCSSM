import pytest
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError

from flask import session

from backend.bcssm_backend import create_app
from backend.bcssm_backend.auth import get_username_from_request, get_user_id_from_request


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    return create_app()


@pytest.fixture
def mock_execute_query(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("backend.bcssm_backend.auth.execute_query", mock)
    return mock


# ─── get_username_from_request ────────────────────────────────────────────────
# Only the session is trusted; all client-supplied values are ignored.

def test_username_from_session(app):
    with app.test_request_context('/test'):
        session['user_name'] = 'Eve'
        assert get_username_from_request() == 'Eve'


def test_username_none_when_missing(app):
    with app.test_request_context('/test'):
        assert get_username_from_request() is None


def test_post_body_not_trusted(app):
    """POST body user_name is ignored — session is the only trusted source."""
    with app.test_request_context('/test', method='POST', json={'user_name': 'Alice'}):
        assert get_username_from_request() is None


def test_query_param_not_trusted(app):
    """Query-param user_name is ignored to prevent impersonation."""
    with app.test_request_context('/test?user_name=Bob'):
        assert get_username_from_request() is None


def test_header_not_trusted(app):
    """X-Current-User header is ignored to prevent impersonation."""
    with app.test_request_context('/test', headers={'X-Current-User': 'Dave'}):
        assert get_username_from_request() is None


# ─── get_user_id_from_request ─────────────────────────────────────────────────

def test_user_id_found_via_session(app, mock_execute_query):
    mock_execute_query.return_value = [(42,)]
    with app.test_request_context('/test'):
        session['user_name'] = 'Alice'
        assert get_user_id_from_request() == 42


def test_user_id_not_found_via_session(app, mock_execute_query):
    mock_execute_query.return_value = []
    with app.test_request_context('/test'):
        session['user_name'] = 'Alice'
        assert get_user_id_from_request() is None


def test_user_id_db_error_reraised(app, mock_execute_query):
    mock_execute_query.side_effect = SQLAlchemyError("db down")
    with app.test_request_context('/test'):
        session['user_name'] = 'Alice'
        with pytest.raises(SQLAlchemyError):
            get_user_id_from_request()


def test_user_id_no_username_returns_none(app, mock_execute_query):
    with app.test_request_context('/test'):
        assert get_user_id_from_request() is None
    mock_execute_query.assert_not_called()


def test_user_id_falls_back_to_session_user_id(app, mock_execute_query):
    """When no user_name in session, fall back to session user_id."""
    with app.test_request_context('/test'):
        session['user_id'] = 99
        assert get_user_id_from_request() == 99
    mock_execute_query.assert_not_called()
