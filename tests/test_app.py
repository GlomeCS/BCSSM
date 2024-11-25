import os
import unittest
from app import app

class TestAppConfig(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    def test_development_config(self):
        os.environ['FLASK_ENV'] = 'development'
        self.app.config.from_object('config.DevelopmentConfig')
        self.assertTrue(self.app.config['DEBUG'])
        self.assertEqual(self.app.config['ENV'], 'development')

    def test_testing_config(self):
        os.environ['FLASK_ENV'] = 'testing'
        self.app.config.from_object('config.TestingConfig')
        self.assertTrue(self.app.config['TESTING'])
        self.assertEqual(self.app.config['ENV'], 'testing')

    def test_production_config(self):
        os.environ['FLASK_ENV'] = 'production'
        self.app.config.from_object('config.ProductionConfig')
        self.assertFalse(self.app.config['DEBUG'])
        self.assertEqual(self.app.config['ENV'], 'production')

if __name__ == '__main__':
    unittest.main()