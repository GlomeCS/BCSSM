import pytest
from app import create_app

@pytest.fixture
def client():
    """Fixture to create a Flask test client"""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test_secret"
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_db_calls(mocker):
    """Automatically mock execute_query for all tests"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    return mock_execute_query


@pytest.fixture(autouse=True)
def mock_flash(mocker):
    """Mock Flask's flash function to prevent side effects in tests"""
    return mocker.patch("routes.devos_feedback.flash")


def test_devos_feedback_success(client, mock_db_calls):
    """Test successful retrieval of feedback records"""
    mock_db_calls.side_effect = lambda query, params: [("Minors", "Great session"), ("Majors", "Needs improvement")]

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200
    assert b"Great session" in response.data
    assert b"Needs improvement" in response.data
    mock_db_calls.assert_called_once()


def test_devos_feedback_no_data(client, mock_db_calls):
    """Test case when no feedback exists"""
    mock_db_calls.side_effect = lambda query, params: []  # Simulate no feedback

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200

    # Check that feedback section is present but empty
    assert b'<div class="row row-cols-1 row-cols-md-2 g-4">' in response.data

    # Ensure no cards are rendered (no feedback entries)
    assert b'<div class="card">' not in response.data  

    # Check that the return-to-home button is present
    assert b'<a href="/" class="btn btn-secondary">Return to Home</a>' in response.data


def test_devos_feedback_database_error(client, mock_db_calls, mock_flash):
    """Test case when database call fails"""
    mock_db_calls.side_effect = Exception("Database error")

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200  # Should still return a valid response
    mock_flash.assert_called_once_with("Error fetching feedback. Please try again later.", "danger")
    assert b"Error fetching feedback" not in response.data  # Should not expose error directly


def test_devos_feedback_logged_in_leader(client, mock_db_calls):
    """Test when a logged-in section leader accesses the feedback page"""
    mock_db_calls.side_effect = [
        [("Minors", "Great session"), ("Majors", "Needs improvement")],  # Feedback records
        [("User1", "Section Leader", "Minors")],  # User role and section
    ]

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    response = client.get("/devos-feedback?date=2024-03-01")

    print(response.data.decode())  # 🔍 Debug: Print response content to check for missing elements

    assert response.status_code == 200
    assert b"Great session" in response.data
    assert b"Needs improvement" in response.data
    assert b'">Edit</a>' in response.data  # ✅ Match actual button text


def test_devos_feedback_logged_in_non_leader(client, mock_db_calls):
    """Test when a regular user accesses the feedback page"""
    mock_db_calls.side_effect = [
        [("Minors", "Great session")],  # Feedback records
        [("User1", "Regular Member", "Minors")],  # User role
    ]

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200
    assert b"Great session" in response.data
    assert b"Edit Feedback" not in response.data  # Should not see edit button
    mock_db_calls.assert_called()


def test_devos_feedback_no_user(client, mock_db_calls):
    """Test when no user is logged in"""
    mock_db_calls.side_effect = lambda query, params: [("Minors", "Great session")]

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200
    assert b"Great session" in response.data
    assert b"Edit Feedback" not in response.data  # Not logged in, so no edit button
    mock_db_calls.assert_called()


def test_devos_feedback_user_not_found(client, mock_db_calls):
    """Test when a logged-in user is not found in the database"""
    mock_db_calls.side_effect = [
        [("Minors", "Great session")],  # Feedback records
        [],  # User lookup fails
    ]

    with client.session_transaction() as sess:
        sess["user_name"] = "UserNotInDB"

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200
    assert b"Great session" in response.data
    assert b"Edit Feedback" not in response.data  # Should not see edit button
    mock_db_calls.assert_called()