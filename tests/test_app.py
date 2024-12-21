import os
import unittest
from unittest import TestCase
from app import create_app
from config import DevelopmentConfig, TestingConfig, ProductionConfig


class TestApp(TestCase):
    def setUp(self):
        self.original_env = os.environ.get('FLASK_ENV')  # Save the original environment variable
        self.app = create_app()  # Use the factory to create the app instance
        self.client = self.app.test_client()

    def tearDown(self):
        if self.original_env is not None:
            os.environ['FLASK_ENV'] = self.original_env
        else:
            os.environ.pop('FLASK_ENV', None)  # Safely remove the key if it exists

    def test_development_config(self):
        os.environ['FLASK_ENV'] = 'development'
        app = create_app()  # Create a new app instance
        self.assertTrue(app.config['DEBUG'])
        self.assertFalse(app.config['TESTING'])

    def test_testing_config(self):
        os.environ['FLASK_ENV'] = 'testing'
        app = create_app()  # Create a new app instance
        self.assertTrue(app.config['TESTING'])
        self.assertFalse(app.config['DEBUG'])

    def test_production_config(self):
        os.environ['FLASK_ENV'] = 'production'
        app = create_app()  # Create a new app instance
        self.assertFalse(app.config['DEBUG'])
        self.assertFalse(app.config['TESTING'])

    def test_default_to_development_config(self):
        # Unset FLASK_ENV safely
        if 'FLASK_ENV' in os.environ:
            del os.environ['FLASK_ENV']

        print("LOGGING: FLASK_ENV in test:", os.environ.get('FLASK_ENV'))

        # Create a new app instance and check the config
        app = create_app()
        self.assertTrue(app.config['DEBUG'])
        self.assertFalse(app.config['TESTING'])


if __name__ == '__main__':
    unittest.main()