import unittest
import os
from flask import Flask, session
from routes import init_routes
from utils import user_assignments

class TestRoutes(unittest.TestCase):

    def setUp(self):
        template_dir = os.path.abspath('templates')
        self.app = Flask(__name__, template_folder=template_dir)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'secret'
        init_routes(self.app)
        self.client = self.app.test_client()

    def test_index(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<select', response.data)  # Assuming there's a dropdown in the index.html

    def test_duty_team_with_user(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Alice'
            response = client.get('/duty-teams')
            self.assertEqual(response.status_code, 200)
            # No need to assert on HTML content

    def test_duty_team_without_user(self):
        response = self.client.get('/duty-teams')
        self.assertEqual(response.status_code, 302)  # Redirect to index
        self.assertIn('/', response.headers['Location'])  # Check for root path

    def test_users_by_section(self):
        response = self.client.get('/users-by-section?section=Minis')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Alice', response.data)  # Adjust based on actual response content

    def test_user_duty(self):
        response = self.client.get('/user-duty?user=Alice')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Minis', response.data)  # Adjust based on actual response content

    def test_select_user_valid(self):
        response = self.client.post('/select-user', json={"user_name": "Alice"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"User Alice selected successfully!", response.data)

    def test_select_user_invalid(self):
        response = self.client.post('/select-user', json={"user_name": "Unknown"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"User not found", response.data)

    def test_get_selected_user_with_user(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Alice'
            response = client.get('/get-selected-user')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {"user": "Alice"})

    def test_get_selected_user_without_user(self):
        response = self.client.get('/get-selected-user')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"user": None})

    def test_logout(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Alice'
            response = client.post('/logout')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"User logged out successfully!", response.data)
            self.assertNotIn('user_name', session)

    def test_devos_feedback(self):
        response = self.client.get('/devos-feedback')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Devo\'s Feedback', response.data)  # Adjust based on actual response content

if __name__ == '__main__':
    unittest.main()