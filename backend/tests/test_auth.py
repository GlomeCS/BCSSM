import pytest
from flask import g, session

from backend.bcssm_backend import create_app
from backend.bcssm_backend.decorators import require_auth


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    return create_app()


def _make_protected_route(app):
    """Register a test route protected by @require_auth."""
    @app.route('/test-auth')
    @require_auth
    def protected():
        return {'user_name': g.user_name, 'user_id': g.user_id}, 200


# ─── require_auth ────────────────────────────────────────────────────────────

def test_require_auth_sets_g_from_session(app):
    _make_protected_route(app)
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Alice'
            sess['user_id'] = 42
        response = client.get('/test-auth')
        assert response.status_code == 200
        data = response.get_json()
        assert data['user_name'] == 'Alice'
        assert data['user_id'] == 42


def test_require_auth_returns_401_when_no_session(app):
    _make_protected_route(app)
    with app.test_client() as client:
        response = client.get('/test-auth')
        assert response.status_code == 401
        assert 'error' in response.get_json()


def test_require_auth_user_id_none_when_not_in_session(app, monkeypatch):
    """user_id absent from session and DB lookup returns None → 401."""
    monkeypatch.setattr(
        "backend.bcssm_backend.user_queries.get_user_id_by_name",
        lambda name: None,
    )
    _make_protected_route(app)
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_name'] = 'Bob'
        response = client.get('/test-auth')
        assert response.status_code == 401
        assert 'error' in response.get_json()


def test_require_auth_ignores_query_param(app):
    _make_protected_route(app)
    with app.test_client() as client:
        response = client.get('/test-auth?user_name=Eve')
        assert response.status_code == 401


def test_require_auth_ignores_header(app):
    _make_protected_route(app)
    with app.test_client() as client:
        response = client.get('/test-auth', headers={'X-Current-User': 'Dave'})
        assert response.status_code == 401
