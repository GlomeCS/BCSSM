import os
from unittest.mock import patch
from urllib.parse import quote


import pytest

from app import create_app


@pytest.fixture(autouse=True)
def mock_db_calls():
    # Mock execute_query
    with patch('utils.execute_query') as mock_execute_query:
        mock_execute_query.side_effect = AssertionError("Database access attempted during test!")

        # Mock db.session
        with patch('globals.db.session') as mock_db_session:
            mock_db_session.execute.side_effect = AssertionError("Database access attempted during test!")
            yield

@pytest.fixture(autouse=True)
def mock_env_vars(mocker):
    # Mock environment variables
    mocker.patch.dict(os.environ, {
        "user": "test_user",
        "password": "test_password",
        "host": "localhost",
        "port": "5432",
        "database": "test_db"
    })

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret'
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_index(client, mocker):
    # Mock get_all_users
    mock_get_all_users = mocker.patch('routes.routes.get_all_users')
    mock_get_all_users.return_value = ['User1', 'User2']

    response = client.get('/')
    assert response.status_code == 200
    assert b'--Select a user--' in response.data
    assert b'User1' in response.data
    assert b'User2' in response.data
    mock_get_all_users.assert_called_once()


def test_login_valid_user(client, mocker):
    mocker.patch('routes.routes.user_assignments', {'User1': {'section': 'Team1'}})

    response = client.post('/login', data={'user_name': 'User1'}, follow_redirects=True)
    assert response.status_code == 200

    with client.session_transaction() as sess:
        assert sess['user_name'] == 'User1'


def test_login_invalid_user(client, mocker):
    mocker.patch('routes.routes.user_assignments', {'User1': {'section': 'Team1'}})

    response = client.post('/login', data={'user_name': 'InvalidUser'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'--Select a user--' in response.data

    with client.session_transaction() as sess:
        assert 'user_name' not in sess


def test_duty_team_with_user(client, mocker):
    mock_get_user_duty = mocker.patch('routes.routes.get_user_duty')
    mock_get_user_duty.return_value = {'duty': 'Test Duty'}

    with client.session_transaction() as sess:
        sess['user_name'] = 'User1'

    response = client.get('/duty-teams')
    assert response.status_code == 200
    assert b'Test Duty' in response.data
    mock_get_user_duty.assert_called_once_with('User1')


def test_duty_team_with_user_no_duty(client, mocker):
    mock_get_user_duty = mocker.patch('routes.routes.get_user_duty')
    mock_get_user_duty.return_value = None  # Simulate no duty

    with client.session_transaction() as sess:
        sess['user_name'] = 'User1'

    response = client.get('/duty-teams')
    assert response.status_code == 200
    assert b'You do not have a duty today.' in response.data
    mock_get_user_duty.assert_called_once_with('User1')


def test_duty_team_without_user(client):
    response = client.get('/duty-teams', follow_redirects=True)
    assert response.status_code == 200
    assert b'--Select a user--' in response.data

def test_login_invalid_target_redirects_to_root(client, mocker):
    """Test that login redirects to '/' when given an external target URL"""
    mocker.patch('routes.routes.user_assignments', {'User1': {'section': 'Team1'}})
    
    # Mock `print` to check if the correct log message is printed
    mock_print = mocker.patch("builtins.print")

    # Simulate an invalid target (external URL)
    invalid_target = "https://malicious-site.com"
    encoded_target = quote(invalid_target)  # Encode the URL to simulate a real request

    response = client.post(f'/login?target={encoded_target}', data={'user_name': 'User1'}, follow_redirects=False)

    # Ensure response is a redirect (302) to the root ("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    # Verify the correct debug log is printed
    mock_print.assert_any_call("Target invalid, redirecting to '/'")