import pytest
from flask import Flask
from routes.users import init_users_routes


@pytest.fixture
def client():
    """Flask test client fixture"""
    app = Flask(__name__)
    app.secret_key = "test_secret"
    init_users_routes(app)
    return app.test_client()


def test_users_by_section_success(client, mocker):
    """Test users_by_section returns expected users"""
    mock_get_users_by_section = mocker.patch("routes.users.get_users_by_section")
    mock_get_users_by_section.return_value = [{"name": "Alice", "role": "Leader"}]

    response = client.get("/users-by-section?section=Minors")
    assert response.status_code == 200
    assert response.is_json
    assert response.json == {"users": [{"name": "Alice", "role": "Leader"}]}


def test_users_by_section_failure(client, mocker):
    """Test users_by_section handles exceptions correctly"""
    mock_get_users_by_section = mocker.patch("routes.users.get_users_by_section")
    mock_get_users_by_section.side_effect = Exception("Database error")

    response = client.get("/users-by-section?section=Minors")

    assert response.status_code == 500
    assert response.mimetype == "application/json"  # Ensure it's JSON
    assert response.json is not None
    assert "error" in response.json



def test_user_duty_success(client, mocker):
    """Test user_duty returns expected duty data"""
    mock_get_user_duty = mocker.patch("routes.users.get_user_duty")
    mock_get_user_duty.return_value = {"user": "Alice", "duty": "Cleaning"}

    response = client.get("/user-duty?user=Alice")
    assert response.status_code == 200
    assert response.is_json
    assert response.json == {"user": "Alice", "duty": "Cleaning"}


def test_user_duty_failure(client, mocker):
    """Test user_duty handles exceptions correctly"""
    mock_get_user_duty = mocker.patch("routes.users.get_user_duty")
    mock_get_user_duty.side_effect = Exception("Database error")

    response = client.get("/user-duty?user=Alice")

    assert response.status_code == 500
    assert response.mimetype == "application/json"  # Ensure it's JSON
    assert response.json is not None
    assert "error" in response.json


def test_select_user_success(client, mocker):
    """Test select_user sets user in session"""
    mock_cache = mocker.patch("routes.users.cache")
    mock_cache.get.return_value = ["Alice", "Bob"]

    with client.application.test_request_context():
        response = client.post("/select-user", json={"user_name": "Alice"})
        assert response.status_code == 200
        assert response.json == {"message": "User Alice successfully selected."}

        # Ensure session updates properly
        with client.session_transaction() as sess:
            assert sess.get("user_name") == "Alice"


def test_select_user_invalid_user(client, mocker):
    """Test select_user rejects invalid user"""
    mock_cache = mocker.patch("routes.users.cache")
    mock_cache.get.return_value = ["Alice", "Bob"]

    with client.application.test_request_context():
        response = client.post("/select-user", json={"user_name": "Charlie"})
        assert response.status_code == 400
        assert response.json == {"message": "Invalid user selected."}

        # Ensure session is not modified
        with client.session_transaction() as sess:
            assert sess.get("user_name") is None


def test_get_selected_user(client):
    """Test get_selected_user returns the logged-in user"""
    with client.session_transaction() as sess:
        sess["user_name"] = "Alice"

    response = client.get("/get-selected-user")
    assert response.status_code == 200
    assert response.is_json
    assert response.json == {"user": "Alice"}


def test_get_selected_user_no_user(client):
    """Test get_selected_user when no user is logged in"""
    response = client.get("/get-selected-user")
    assert response.status_code == 200
    assert response.is_json
    assert response.json == {"user": None}


def test_logout(client):
    """Test logout removes user from session"""
    with client.application.test_request_context(), client.session_transaction() as sess:
        sess["user_name"] = "Alice"

        response = client.post("/logout")
        assert response.status_code == 200
        assert response.is_json
        assert response.json == {"message": "User logged out successfully!"}

        # Ensure session is cleared
        with client.session_transaction() as sess:
            assert sess.get("user_name") is None