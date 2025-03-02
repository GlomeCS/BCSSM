import pytest
from unittest.mock import patch, MagicMock
from flask import session
from app import create_app


@pytest.fixture
def client():
    """Fixture to create a Flask test client"""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test_secret"
    return app.test_client()


def test_devos_feedback_success(client, mocker):
    """Test fetching devotional feedback successfully"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    mock_execute_query.return_value = [("Minors", "Great session"), ("Majors", "Needs improvement")]

    response = client.get("/devos-feedback?date=2024-03-01")
    
    assert response.status_code == 200
    assert b"Great session" in response.data
    assert b"Needs improvement" in response.data
    mock_execute_query.assert_called_once()


def test_devos_feedback_no_data(client, mocker):
    """Test fetching devotional feedback when no data exists"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    mock_execute_query.return_value = []  # No feedback data

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200
    assert b"Great session" not in response.data  # Ensure no data is displayed
    assert b"Needs improvement" not in response.data
    mock_execute_query.assert_called_once()


def test_devos_feedback_database_error(client, mocker):
    """Test handling database failure when fetching devotional feedback"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    mock_execute_query.side_effect = Exception("Database error")

    response = client.get("/devos-feedback?date=2024-03-01")

    assert response.status_code == 200  # Still returns a page
    assert b"Failed to fetch feedback records" not in response.data  # Error is logged, not displayed


def test_devos_feedback_edit_access_denied(client, mocker):
    """Test unauthorized user attempting to access edit feedback page"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    mock_execute_query.return_value = [("1", "Regular Member", "Minors")]

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    response = client.get("/devos-feedback/edit?date=2024-03-01&section=Majors")

    assert response.status_code == 403
    assert b"Not authorized" in response.data

def test_devos_feedback_edit_success(client, mocker):
    """Test section leader editing devotional feedback successfully"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    mock_execute_query.side_effect = [
        [("1", "Section Leader", "Minors")],  # User role lookup
        [("1")],  # Section lookup
        [("Previous feedback",)],  # Corrected structure for previous feedback
    ]

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    response = client.get("/devos-feedback/edit?date=2024-03-01&section=Minors")

    assert response.status_code == 200
    assert b"Previous feedback" in response.data  # Ensure previous feedback is displayed


def test_devos_feedback_edit_post_database_error(client, mocker):
    """Test handling database failure when updating feedback"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    mock_execute_query.side_effect = [
        [("1", "Section Leader", "Minors")],  # User role lookup
        [("1")],  # Section lookup
        Exception("Database error"),
    ]

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    response = client.post(
        "/devos-feedback/edit?date=2024-03-01&section=Minors",
        data={"feedback": "New session feedback"},
        follow_redirects=False,
    )

    assert response.status_code == 500
    assert b"Error updating feedback" in response.data
    mock_execute_query.assert_called()


def test_devos_feedback_edit_no_date_section(client):
    """Test attempting to edit feedback without specifying a date and section"""
    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    response = client.get("/devos-feedback/edit")

    assert response.status_code == 302  # Redirects to main feedback page


def test_devos_feedback_edit_user_not_found(client, mocker):
    """Test handling case where user is not found in the database"""
    mock_execute_query = mocker.patch("routes.devos_feedback.execute_query")
    mock_execute_query.return_value = []  # User not found

    with client.session_transaction() as sess:
        sess["user_name"] = "User1"

    response = client.get("/devos-feedback/edit?date=2024-03-01&section=Minors")

    assert response.status_code == 403
    assert b"User not found" in response.data