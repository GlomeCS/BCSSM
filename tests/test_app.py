import logging
import os
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app import configure_logging, create_app


@pytest.fixture(scope="function")
def clean_env():
    """Fixture to clean and restore environment variables after each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_db_cache():
    """Fixture to mock database and cache."""
    with patch('app.db') as mock_db, patch('app.cache') as mock_cache:
        mock_db.init_app = MagicMock()
        mock_cache.init_app = MagicMock()
        yield mock_db, mock_cache


def test_create_app_with_valid_env_vars(clean_env, mock_db_cache):
    """Test that create_app initializes correctly with valid environment variables."""
    os.environ['FLASK_ENV'] = 'testing'  # ✅ Ensure it's in testing mode
    os.environ['user'] = 'test_user'
    os.environ['password'] = 'test_password'
    os.environ['host'] = 'localhost'
    os.environ['database'] = 'test_db'

    mock_db, mock_cache = mock_db_cache
    app = create_app()

    assert isinstance(app, Flask)
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'postgresql://test_user:test_password@localhost:5432/test_db'
    assert app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] is False

    # ✅ Only check init_app if NOT in testing mode
    if not app.config.get("TESTING"):
        mock_db.init_app.assert_called_once_with(app)
    else:
        mock_db.init_app.assert_not_called()  # ✅ Ensure it's not called in testing mode


@patch.dict(os.environ, {}, clear=True)
@patch('app.load_dotenv')
def test_create_app_missing_env_vars_raises_error(mock_load_dotenv):
    """Test that create_app raises an error when required env vars are missing."""
    mock_load_dotenv.return_value = None

    with pytest.raises(RuntimeError, match="Missing required database environment variables."):
        create_app()


@patch('logging.basicConfig')
@patch('logging.getLogger')
def test_configure_logging(mock_get_logger, mock_basic_config):
    """Test that logging is configured correctly."""
    app = MagicMock()
    app.logger.setLevel = MagicMock()

    configure_logging(app)

    mock_basic_config.assert_called_once_with(
        level=logging.DEBUG,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )
    app.logger.setLevel.assert_called_once_with(logging.DEBUG)

@pytest.mark.parametrize("env, expected_env, expected_debug", [
    ("production", "production", False),  # Production case
    ("unknown_env", "development", True),  # Fallback to development
])
def test_create_app_config(clean_env, mock_db_cache, monkeypatch, env, expected_env, expected_debug):
    """Test that create_app() applies the correct config based on FLASK_ENV."""
    monkeypatch.setenv("FLASK_ENV", env)  # Mock FLASK_ENV
    monkeypatch.setenv("user", "test_user")
    monkeypatch.setenv("password", "test_password")
    monkeypatch.setenv("host", "localhost")
    monkeypatch.setenv("database", "test_db")

    mock_db, mock_cache = mock_db_cache  # Use mocked db and cache

    app = create_app()

    expected_db_uri = f"postgresql://test_user:test_password@localhost:5432/test_db"

    assert app.config["ENV"] == expected_env  # Check the environment variable was applied
    assert app.config["DEBUG"] == expected_debug  # Check DEBUG mode
    assert app.config["SQLALCHEMY_DATABASE_URI"] == expected_db_uri  # Ensure correct DB URI
    assert isinstance(app.config, dict)  # Ensure app config is loaded correctly

    mock_db.init_app.assert_called_once_with(app)
    mock_cache.init_app.assert_called_once_with(app)