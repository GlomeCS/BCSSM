import os
import unittest
import logging
from unittest.mock import patch, MagicMock
from app import create_app, configure_logging
from flask import Flask

class TestApp(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch('app.db')  # Correct patch path
    @patch('app.cache')  # Correct patch path
    def test_create_app_with_valid_env_vars(self, mock_cache, mock_db):
        # Set required environment variables
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['user'] = 'test_user'
        os.environ['password'] = 'test_password'
        os.environ['host'] = 'localhost'
        os.environ['database'] = 'test_db'

        # Mock database and cache initialization
        mock_db.init_app = MagicMock()
        mock_cache.init_app = MagicMock()

        # Create the app
        app = create_app()

        # Assert the app is configured correctly
        self.assertIsInstance(app, Flask)
        self.assertEqual(app.config['SQLALCHEMY_DATABASE_URI'],
                        'postgresql://test_user:test_password@localhost:5432/test_db')
        self.assertFalse(app.config['SQLALCHEMY_TRACK_MODIFICATIONS'])

        # Ensure init_app was called
        mock_db.init_app.assert_called_once_with(app)
        mock_cache.init_app.assert_called_once_with(app)

    @patch.dict(os.environ, {}, clear=True)  # Clear the environment variables
    @patch('app.load_dotenv')  # Mock load_dotenv to prevent .env loading
    def test_create_app_missing_env_vars_raises_error(self, mock_load_dotenv):
        mock_load_dotenv.return_value = None  # Mock load_dotenv to do nothing

        with self.assertRaises(RuntimeError) as context:
            create_app()

        # Confirm the error message
        self.assertEqual(str(context.exception), "Missing required database environment variables.")

    @patch('logging.basicConfig')
    @patch('logging.getLogger')
    def test_configure_logging(self, mock_get_logger, mock_basic_config):
        app = MagicMock()
        app.logger.setLevel = MagicMock()

        configure_logging(app)

        # Assert logging is configured with the correct format
        mock_basic_config.assert_called_once_with(
            level=logging.DEBUG,
            format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        )
        app.logger.setLevel.assert_called_once_with(logging.DEBUG)