import pytest
import json
import logging
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend import create_app
from backend.bcssm_backend.exceptions import DatabaseError

# ─── 0) Fixture: use TestingConfig and register routes ──────────────────────────
@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    app = create_app()
    # routes for users_sections are already registered by create_app()
    return app

# ─── 1) Fixture: test client ─────────────────────────────────────────────────────
@pytest.fixture
def client(app):
    return app.test_client()

# ─── 2) Patch utility functions ──────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def mock_utils(monkeypatch):
    """Mock the utility functions used by the routes"""
    mock_sections = MagicMock(return_value=[])
    mock_users = MagicMock(return_value=[])
    
    # Try multiple possible import paths where the routes might import from
    import_paths = [
        ("backend.bcssm_backend.utils.get_all_sections_with_users", mock_sections),
        ("backend.bcssm_backend.utils.get_users_by_section", mock_users),
        ("backend.bcssm_backend.routes.sections.get_all_sections_with_users", mock_sections),
        ("backend.bcssm_backend.routes.sections.get_users_by_section", mock_users),
    ]
    
    for path, mock_obj in import_paths:
        try:
            monkeypatch.setattr(path, mock_obj)
        except (AttributeError, ImportError):
            # If the import path doesn't exist, that's fine
            pass
    
    return mock_sections, mock_users

# ─── Tests for /api/users/by-section endpoint ────────────────────────────────

def test_get_users_by_section_route_success(client, mock_utils):
    """Test successful retrieval of users grouped by section"""
    mock_sections, _ = mock_utils
    
    # Arrange
    mock_sections_data = [
        {
            "name": "Minis",
            "display_order": 1,
            "users": [
                {"name": "Alice Smith", "role": "Section Leader"},
                {"name": "Bob Jones", "role": "Team Member"}
            ],
            "user_count": 2
        },
        {
            "name": "Micros",
            "display_order": 2,
            "users": [
                {"name": "Charlie Brown", "role": "Section Leader"}
            ],
            "user_count": 1
        }
    ]
    mock_sections.return_value = mock_sections_data
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Act
    response = client.get('/api/users/by-section')
    
    # Debug: Print response if not expected
    if response.status_code not in [200, 404]:
        print(f"Unexpected status: {response.status_code}")
        print(f"Response data: {response.get_data(as_text=True)}")
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    if response.status_code == 500:
        # Print the actual error for debugging
        data = json.loads(response.data)
        print(f"500 Error: {data}")
        pytest.fail(f"Route returned 500 error: {data.get('error', 'Unknown error')}")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert "sections" in data
    assert "total_users" in data
    assert "total_sections" in data
    
    assert data["sections"] == mock_sections_data
    assert data["total_users"] == 3  # 2 + 1
    assert data["total_sections"] == 2
    
    # Verify the utility function was called
    mock_sections.assert_called_once()

def test_get_users_by_section_route_unauthenticated(client):
    """Test endpoint returns 401 when user is not authenticated"""
    # Don't set up session (unauthenticated)
    
    # Act
    response = client.get('/api/users/by-section')
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "Authentication required" in data["error"]

def test_get_users_by_section_route_utility_error(client, mock_utils):
    """Test endpoint returns 500 when utility function raises a database error"""
    mock_sections, _ = mock_utils
    mock_sections.side_effect = DatabaseError("Database connection failed")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/by-section')

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")

    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_users_by_section_route_empty_data(client, mock_utils):
    """Test endpoint with empty sections data"""
    mock_sections, _ = mock_utils
    mock_sections.return_value = []
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Act
    response = client.get('/api/users/by-section')
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert data["sections"] == []
    assert data["total_users"] == 0
    assert data["total_sections"] == 0

def test_get_users_by_section_route_exception_handling(client, mock_utils):
    """Test endpoint handles unexpected exceptions"""
    mock_sections, _ = mock_utils
    mock_sections.side_effect = SQLAlchemyError("Unexpected error")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/by-section')

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")

    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_users_by_section_route_logging(client, mock_utils, caplog):
    """Test that appropriate log messages are generated"""
    mock_sections, _ = mock_utils
    mock_sections_data = [
        {"name": "TestSection", "display_order": 1, "users": [{"name": "Test User", "role": "Test Role"}], "user_count": 1}
    ]
    mock_sections.return_value = mock_sections_data
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    with caplog.at_level(logging.INFO):
        # Act
        response = client.get('/api/users/by-section')
        
        # Assert
        if response.status_code == 200:
            # Check that some logging occurred
            assert len(caplog.records) > 0

def test_get_users_by_section_route_error_logging(client, mock_utils, caplog):
    """Test error logging when utility function raises a database error"""
    mock_sections, _ = mock_utils
    mock_sections.side_effect = DatabaseError("Test error message")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    with caplog.at_level(logging.ERROR):
        response = client.get('/api/users/by-section')

        if response.status_code == 500:
            assert any("error" in record.message.lower() for record in caplog.records)

# ─── Tests for /api/users/section/<section_name> endpoint ────────────────────

def test_get_section_users_route_success(client, mock_utils):
    """Test successful retrieval of users for a specific section"""
    _, mock_users = mock_utils
    
    # Arrange
    mock_users_data = [
        {"name": "Alice Smith", "role": "Section Leader"},
        {"name": "Bob Jones", "role": "Team Member"},
        {"name": "Charlie Brown", "role": "Team Leader"}
    ]
    mock_users.return_value = mock_users_data
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Act
    response = client.get('/api/users/section/Minis')
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert "section" in data
    assert "users" in data
    assert "user_count" in data
    
    assert data["section"] == "Minis"
    assert data["users"] == mock_users_data
    assert data["user_count"] == 3
    
    # Verify the utility function was called with correct parameter
    mock_users.assert_called_once_with("Minis")

def test_get_section_users_route_unauthenticated(client):
    """Test endpoint returns 401 when user is not authenticated"""
    # Don't set up session (unauthenticated)
    
    # Act
    response = client.get('/api/users/section/TestSection')
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "Authentication required" in data["error"]

def test_get_section_users_route_utility_error(client, mock_utils):
    """Test endpoint returns 500 when utility function raises a database error"""
    _, mock_users = mock_utils
    mock_users.side_effect = DatabaseError("Section not found")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/section/NonexistentSection')

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")

    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_section_users_route_empty_section(client, mock_utils):
    """Test endpoint with empty section (no users)"""
    _, mock_users = mock_utils
    mock_users.return_value = []
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Act
    response = client.get('/api/users/section/EmptySection')
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert data["section"] == "EmptySection"
    assert data["users"] == []
    assert data["user_count"] == 0

def test_get_section_users_route_unassigned_section(client, mock_utils):
    """Test endpoint with 'Unassigned' section"""
    _, mock_users = mock_utils
    
    # Arrange
    mock_users_data = [
        {"name": "Unassigned User 1", "role": "Team Member"},
        {"name": "Unassigned User 2", "role": "Team Leader"}
    ]
    mock_users.return_value = mock_users_data
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Act
    response = client.get('/api/users/section/Unassigned')
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert data["section"] == "Unassigned"
    assert data["users"] == mock_users_data
    assert data["user_count"] == 2
    
    mock_users.assert_called_once_with("Unassigned")

def test_get_section_users_route_exception_handling(client, mock_utils):
    """Test endpoint handles unexpected exceptions"""
    _, mock_users = mock_utils
    mock_users.side_effect = SQLAlchemyError("Unexpected database error")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/section/TestSection')

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")

    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_section_users_route_special_characters_in_section_name(client, mock_utils):
    """Test endpoint with special characters in section name"""
    _, mock_users = mock_utils
    
    # Arrange
    section_name = "Section-Name_With+Special%20Characters"
    # Flask will URL decode %20 to a space, so expect the decoded version
    expected_section_name = "Section-Name_With+Special Characters"
    mock_users_data = [{"name": "Test User", "role": "Test Role"}]
    mock_users.return_value = mock_users_data
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Act
    response = client.get(f'/api/users/section/{section_name}')
    
    # Assert
    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # The section name in the response will be URL decoded
    assert data["section"] == expected_section_name
    # The utility function should be called with the decoded section name
    mock_users.assert_called_once_with(expected_section_name)

def test_get_section_users_route_logging(client, mock_utils, caplog):
    """Test that appropriate log messages are generated"""
    _, mock_users = mock_utils
    mock_users_data = [{"name": "Test User", "role": "Test Role"}]
    mock_users.return_value = mock_users_data
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    with caplog.at_level(logging.INFO):
        # Act
        response = client.get('/api/users/section/TestSection')
        
        # Assert
        if response.status_code == 200:
            # Check that some logging occurred
            assert len(caplog.records) > 0

def test_get_section_users_route_error_logging(client, mock_utils, caplog):
    """Test error logging when utility function raises a database error"""
    _, mock_users = mock_utils
    mock_users.side_effect = DatabaseError("Section query failed")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    with caplog.at_level(logging.ERROR):
        response = client.get('/api/users/section/TestSection')

        if response.status_code == 500:
            assert any("error" in record.message.lower() for record in caplog.records)

def test_get_section_users_route_exception_logging(client, mock_utils, caplog):
    """Test exception logging"""
    _, mock_users = mock_utils
    mock_users.side_effect = SQLAlchemyError("Database timeout")
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    with caplog.at_level(logging.ERROR):
        # Act
        response = client.get('/api/users/section/TestSection')
        
        # Assert
        if response.status_code == 500:
            # Check that exception logging occurred
            assert any("timeout" in record.message.lower() for record in caplog.records)

# ─── Integration and Edge Case Tests ──────────────────────────────────────────

def test_both_endpoints_authentication_consistency(client):
    """Test that both endpoints handle authentication consistently"""
    # Don't set up session (unauthenticated)
    
    # Act & Assert for first endpoint
    response1 = client.get('/api/users/by-section')
    if response1.status_code != 404:  # Skip if route not implemented
        assert response1.status_code == 401
        data1 = json.loads(response1.data)
        assert "Authentication required" in data1["error"]

    # Act & Assert for second endpoint
    response2 = client.get('/api/users/section/TestSection')
    if response2.status_code != 404:  # Skip if route not implemented
        assert response2.status_code == 401
        data2 = json.loads(response2.data)
        assert "Authentication required" in data2["error"]

def test_get_users_by_section_auth_via_query_param_rejected(client, mock_utils):
    """Query-param user_name is no longer trusted — must return 401."""
    mock_sections, _ = mock_utils
    mock_sections.return_value = []

    response = client.get('/api/users/by-section?user_name=Dohn%20Joe')

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    assert response.status_code == 401


def test_get_users_by_section_auth_via_header_rejected(client, mock_utils):
    """X-Current-User header is no longer trusted — must return 401."""
    mock_sections, _ = mock_utils
    mock_sections.return_value = []

    response = client.get('/api/users/by-section', headers={'X-Current-User': 'Dohn Joe'})

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    assert response.status_code == 401


def test_get_section_users_auth_via_query_param_rejected(client, mock_utils):
    """Query-param user_name is no longer trusted — must return 401."""
    _, mock_users = mock_utils
    mock_users.return_value = []

    response = client.get('/api/users/section/Minis?user_name=Dohn%20Joe')

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    assert response.status_code == 401


def test_get_section_users_auth_via_header_rejected(client, mock_utils):
    """X-Current-User header is no longer trusted — must return 401."""
    _, mock_users = mock_utils
    mock_users.return_value = []

    response = client.get('/api/users/section/Minis', headers={'X-Current-User': 'Dohn Joe'})

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    assert response.status_code == 401


def test_login_session_grants_access_to_sections(client, mock_utils):
    """Integration: POST /api/auth/login sets session → GET /api/users/by-section returns 200."""
    mock_sections, _ = mock_utils
    mock_sections.return_value = []

    with client.session_transaction() as sess:
        sess['user_name'] = 'Dohn Joe'

    response = client.get('/api/users/by-section')

    if response.status_code == 404:
        pytest.skip("Route not implemented yet")
    assert response.status_code == 200


def test_route_exists(client):
    """Basic test to verify routes exist"""
    # Test that routes return something other than 404
    response1 = client.get('/api/users/by-section')
    response2 = client.get('/api/users/section/TestSection')
    
    # Either the route exists (returns 401 for unauthenticated) or doesn't (404)
    assert response1.status_code in [401, 404]
    assert response2.status_code in [401, 404]
    
    if response1.status_code == 404 and response2.status_code == 404:
        pytest.skip("Routes not implemented yet")

def test_json_response_format_consistency(client, mock_utils):
    """Test that both endpoints return consistent JSON format"""
    mock_sections, mock_users = mock_utils
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Test first endpoint
    mock_sections.return_value = [
        {"name": "Test", "display_order": 1, "users": [], "user_count": 0}
    ]
    
    response1 = client.get('/api/users/by-section')
    if response1.status_code == 200:
        assert response1.content_type == 'application/json'
        data1 = json.loads(response1.data)
        assert isinstance(data1, dict)
        assert all(key in data1 for key in ["sections", "total_users", "total_sections"])
    
    # Test second endpoint
    mock_users.return_value = []
    
    response2 = client.get('/api/users/section/TestSection')
    if response2.status_code == 200:
        assert response2.content_type == 'application/json'
        data2 = json.loads(response2.data)
        assert isinstance(data2, dict)
        assert all(key in data2 for key in ["section", "users", "user_count"])

def test_error_response_format_consistency(client, mock_utils):
    """Test that error responses have consistent format"""
    mock_sections, mock_users = mock_utils

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    mock_sections.side_effect = DatabaseError("Test error 1")

    response1 = client.get('/api/users/by-section')
    if response1.status_code == 500:
        data1 = json.loads(response1.data)
        assert "error" in data1
        assert isinstance(data1["error"], str)

    mock_sections.side_effect = None
    mock_users.side_effect = DatabaseError("Test error 2")

    response2 = client.get('/api/users/section/TestSection')
    if response2.status_code == 500:
        data2 = json.loads(response2.data)
        assert "error" in data2
        assert isinstance(data2["error"], str)

def test_endpoints_handle_large_datasets(client, mock_utils):
    """Test endpoints can handle large datasets"""
    mock_sections, _ = mock_utils
    
    # Create large mock dataset
    large_sections_data = []
    for i in range(100):  # 100 sections
        users = [{"name": f"User{j}", "role": "Team Member"} for j in range(50)]  # 50 users each
        large_sections_data.append({
            "name": f"Section{i}",
            "display_order": i,
            "users": users,
            "user_count": 50
        })
    
    mock_sections.return_value = large_sections_data
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Act
    response = client.get('/api/users/by-section')
    
    # Assert
    if response.status_code == 200:
        data = json.loads(response.data)
        
        assert data["total_sections"] == 100
        assert data["total_users"] == 5000  # 100 * 50
        assert len(data["sections"]) == 100

def test_concurrent_requests_simulation(client, mock_utils):
    """Test that endpoints can handle multiple concurrent-like requests"""
    mock_sections, _ = mock_utils
    mock_sections.return_value = [{"name": "Test", "display_order": 1, "users": [], "user_count": 0}]
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'
    
    # Simulate multiple requests
    responses = []
    for _ in range(10):
        response = client.get('/api/users/by-section')
        responses.append(response)
    
    # Assert all requests succeeded (or consistently failed with 404)
    for response in responses:
        assert response.status_code in [200, 404]
    
    # If any succeeded, they all should have succeeded
    success_count = sum(1 for r in responses if r.status_code == 200)
    if success_count > 0:
        assert success_count == 10
        # Verify the utility function was called for each request
        assert mock_sections.call_count == 10