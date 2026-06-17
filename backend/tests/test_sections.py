import pytest
import json
import logging
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend import create_app
from backend.bcssm_backend.exceptions import DatabaseError

# ─── 0) Fixture: use TestingConfig and register routes ──────────────────────────
@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    return create_app()

# ─── 1) Fixture: test client ─────────────────────────────────────────────────────
@pytest.fixture
def client(app):
    return app.test_client()

# ─── 2) Patch utility functions ──────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def mock_utils(monkeypatch):
    mock_sections = MagicMock(return_value=[])
    mock_users = MagicMock(return_value=[])
    monkeypatch.setattr("backend.bcssm_backend.routes.sections.get_all_sections_with_users", mock_sections)
    monkeypatch.setattr("backend.bcssm_backend.routes.sections.get_users_by_section", mock_users)
    monkeypatch.setattr("backend.bcssm_backend.user_queries.get_user_id_by_name", lambda name: 1)
    return mock_sections, mock_users

# ─── Tests for /api/users/by-section endpoint ────────────────────────────────

def test_get_users_by_section_route_success(client, mock_utils):
    mock_sections, _ = mock_utils
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

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/by-section')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert "sections" in data
    assert "total_users" in data
    assert "total_sections" in data
    assert data["sections"] == mock_sections_data
    assert data["total_users"] == 3
    assert data["total_sections"] == 2
    mock_sections.assert_called_once()

def test_get_users_by_section_route_unauthenticated(client):
    response = client.get('/api/users/by-section')
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "Authentication required" in data["error"]

def test_get_users_by_section_route_utility_error(client, mock_utils):
    mock_sections, _ = mock_utils
    mock_sections.side_effect = DatabaseError("Database connection failed")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/by-section')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_users_by_section_route_empty_data(client, mock_utils):
    mock_sections, _ = mock_utils
    mock_sections.return_value = []

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/by-section')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["sections"] == []
    assert data["total_users"] == 0
    assert data["total_sections"] == 0

def test_get_users_by_section_route_exception_handling(client, mock_utils):
    mock_sections, _ = mock_utils
    mock_sections.side_effect = SQLAlchemyError("Unexpected error")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/by-section')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_users_by_section_route_logging(client, mock_utils, caplog):
    mock_sections, _ = mock_utils
    mock_sections.return_value = [
        {"name": "TestSection", "display_order": 1, "users": [{"name": "Test User", "role": "Test Role"}], "user_count": 1}
    ]

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    with caplog.at_level(logging.INFO):
        response = client.get('/api/users/by-section')
        assert response.status_code == 200
        assert len(caplog.records) > 0

def test_get_users_by_section_route_error_logging(client, mock_utils, caplog):
    mock_sections, _ = mock_utils
    mock_sections.side_effect = DatabaseError("Test error message")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    with caplog.at_level(logging.ERROR):
        response = client.get('/api/users/by-section')
        assert response.status_code == 500
        assert any("error" in record.message.lower() for record in caplog.records)

# ─── Tests for /api/users/section/<section_name> endpoint ────────────────────

def test_get_section_users_route_success(client, mock_utils):
    _, mock_users = mock_utils
    mock_users_data = [
        {"name": "Alice Smith", "role": "Section Leader"},
        {"name": "Bob Jones", "role": "Team Member"},
        {"name": "Charlie Brown", "role": "Team Leader"}
    ]
    mock_users.return_value = mock_users_data

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/section/Minis')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert "section" in data
    assert "users" in data
    assert "user_count" in data
    assert data["section"] == "Minis"
    assert data["users"] == mock_users_data
    assert data["user_count"] == 3
    mock_users.assert_called_once_with("Minis")

def test_get_section_users_route_unauthenticated(client):
    response = client.get('/api/users/section/TestSection')
    assert response.status_code == 401
    data = json.loads(response.data)
    assert "Authentication required" in data["error"]

def test_get_section_users_route_utility_error(client, mock_utils):
    _, mock_users = mock_utils
    mock_users.side_effect = DatabaseError("Section not found")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/section/NonexistentSection')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_section_users_route_empty_section(client, mock_utils):
    _, mock_users = mock_utils
    mock_users.return_value = []

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/section/EmptySection')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["section"] == "EmptySection"
    assert data["users"] == []
    assert data["user_count"] == 0

def test_get_section_users_route_unassigned_section(client, mock_utils):
    _, mock_users = mock_utils
    mock_users_data = [
        {"name": "Unassigned User 1", "role": "Team Member"},
        {"name": "Unassigned User 2", "role": "Team Leader"}
    ]
    mock_users.return_value = mock_users_data

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/section/Unassigned')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["section"] == "Unassigned"
    assert data["users"] == mock_users_data
    assert data["user_count"] == 2
    mock_users.assert_called_once_with("Unassigned")

def test_get_section_users_route_exception_handling(client, mock_utils):
    _, mock_users = mock_utils
    mock_users.side_effect = SQLAlchemyError("Unexpected database error")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/section/TestSection')
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["error"] == "Internal server error"

def test_get_section_users_route_special_characters_in_section_name(client, mock_utils):
    _, mock_users = mock_utils
    section_name = "Section-Name_With+Special%20Characters"
    expected_section_name = "Section-Name_With+Special Characters"
    mock_users.return_value = [{"name": "Test User", "role": "Test Role"}]

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get(f'/api/users/section/{section_name}')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["section"] == expected_section_name
    mock_users.assert_called_once_with(expected_section_name)

def test_get_section_users_route_logging(client, mock_utils, caplog):
    _, mock_users = mock_utils
    mock_users.return_value = [{"name": "Test User", "role": "Test Role"}]

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    with caplog.at_level(logging.INFO):
        response = client.get('/api/users/section/TestSection')
        assert response.status_code == 200
        assert len(caplog.records) > 0

def test_get_section_users_route_error_logging(client, mock_utils, caplog):
    _, mock_users = mock_utils
    mock_users.side_effect = DatabaseError("Section query failed")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    with caplog.at_level(logging.ERROR):
        response = client.get('/api/users/section/TestSection')
        assert response.status_code == 500
        assert any("error" in record.message.lower() for record in caplog.records)

def test_get_section_users_route_exception_logging(client, mock_utils, caplog):
    _, mock_users = mock_utils
    mock_users.side_effect = SQLAlchemyError("Database timeout")

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    with caplog.at_level(logging.ERROR):
        response = client.get('/api/users/section/TestSection')
        assert response.status_code == 500
        assert any("timeout" in record.message.lower() for record in caplog.records)

# ─── Integration and Edge Case Tests ──────────────────────────────────────────

def test_both_endpoints_authentication_consistency(client):
    response1 = client.get('/api/users/by-section')
    assert response1.status_code == 401
    assert "Authentication required" in json.loads(response1.data)["error"]

    response2 = client.get('/api/users/section/TestSection')
    assert response2.status_code == 401
    assert "Authentication required" in json.loads(response2.data)["error"]

def test_get_users_by_section_auth_via_query_param_rejected(client, mock_utils):
    """Query-param user_name is no longer trusted — must return 401."""
    response = client.get('/api/users/by-section?user_name=Dohn%20Joe')
    assert response.status_code == 401

def test_get_users_by_section_auth_via_header_rejected(client, mock_utils):
    """X-Current-User header is no longer trusted — must return 401."""
    response = client.get('/api/users/by-section', headers={'X-Current-User': 'Dohn Joe'})
    assert response.status_code == 401

def test_get_section_users_auth_via_query_param_rejected(client, mock_utils):
    """Query-param user_name is no longer trusted — must return 401."""
    response = client.get('/api/users/section/Minis?user_name=Dohn%20Joe')
    assert response.status_code == 401

def test_get_section_users_auth_via_header_rejected(client, mock_utils):
    """X-Current-User header is no longer trusted — must return 401."""
    response = client.get('/api/users/section/Minis', headers={'X-Current-User': 'Dohn Joe'})
    assert response.status_code == 401

def test_login_session_grants_access_to_sections(client, mock_utils):
    """Session → GET /api/users/by-section returns 200."""
    mock_sections, _ = mock_utils
    mock_sections.return_value = []

    with client.session_transaction() as sess:
        sess['user_name'] = 'Dohn Joe'

    response = client.get('/api/users/by-section')
    assert response.status_code == 200

def test_route_exists(client):
    """Unauthenticated requests return 401 (not 404) confirming routes are registered."""
    assert client.get('/api/users/by-section').status_code == 401
    assert client.get('/api/users/section/TestSection').status_code == 401

def test_json_response_format_consistency(client, mock_utils):
    mock_sections, mock_users = mock_utils

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    mock_sections.return_value = [
        {"name": "Test", "display_order": 1, "users": [], "user_count": 0}
    ]
    response1 = client.get('/api/users/by-section')
    assert response1.status_code == 200
    assert response1.content_type == 'application/json'
    data1 = json.loads(response1.data)
    assert all(key in data1 for key in ["sections", "total_users", "total_sections"])

    mock_users.return_value = []
    response2 = client.get('/api/users/section/TestSection')
    assert response2.status_code == 200
    assert response2.content_type == 'application/json'
    data2 = json.loads(response2.data)
    assert all(key in data2 for key in ["section", "users", "user_count"])

def test_error_response_format_consistency(client, mock_utils):
    mock_sections, mock_users = mock_utils

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    mock_sections.side_effect = DatabaseError("Test error 1")
    response1 = client.get('/api/users/by-section')
    assert response1.status_code == 500
    data1 = json.loads(response1.data)
    assert "error" in data1
    assert isinstance(data1["error"], str)

    mock_sections.side_effect = None
    mock_users.side_effect = DatabaseError("Test error 2")
    response2 = client.get('/api/users/section/TestSection')
    assert response2.status_code == 500
    data2 = json.loads(response2.data)
    assert "error" in data2
    assert isinstance(data2["error"], str)

def test_endpoints_handle_large_datasets(client, mock_utils):
    mock_sections, _ = mock_utils
    large_sections_data = [
        {
            "name": f"Section{i}",
            "display_order": i,
            "users": [{"name": f"User{j}", "role": "Team Member"} for j in range(50)],
            "user_count": 50
        }
        for i in range(100)
    ]
    mock_sections.return_value = large_sections_data

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    response = client.get('/api/users/by-section')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["total_sections"] == 100
    assert data["total_users"] == 5000
    assert len(data["sections"]) == 100

def test_concurrent_requests_simulation(client, mock_utils):
    mock_sections, _ = mock_utils
    mock_sections.return_value = [{"name": "Test", "display_order": 1, "users": [], "user_count": 0}]

    with client.session_transaction() as sess:
        sess['user_name'] = 'test_user'

    responses = [client.get('/api/users/by-section') for _ in range(10)]
    assert all(r.status_code == 200 for r in responses)
    assert mock_sections.call_count == 10
