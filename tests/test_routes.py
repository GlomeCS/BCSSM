import unittest
import os
from flask import Flask, session
from unittest.mock import patch
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

    def test_devos_feedback_edit_get(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Alice'
                user_assignments['Alice'] = {'role': 'Section Leader', 'section': 'Minis'}
            response = client.get('/devos-feedback/edit?date=2023-10-10§ion=Minis')
            self.assertEqual(response.status_code, 302)

    def test_devos_feedback_edit_post(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Alice'
                user_assignments['Alice'] = {'role': 'Section Leader', 'section': 'Minis'}
            response = client.post('/devos-feedback/edit?date=2023-10-10§ion=Minis', data={'feedback': 'Great job!'})
            self.assertEqual(response.status_code, 302)  # Redirect after post
            self.assertIn('/devos-feedback', response.headers['Location'])

    def test_devos_feedback_edit_unauthorized(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Bob'
                user_assignments['Bob'] = {'role': 'Team Member', 'section': 'Micros'}
            response = client.get('/devos-feedback/edit?date=2023-10-10§ion=Minis')
            self.assertEqual(response.status_code, 302)  # Forbidden

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

    def test_duty_teams_no_duty(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Alice'  # Simulate logged-in user

            # Use patch to mock the `get_user_duty` function
            with patch('routes.get_user_duty', return_value=None):  # Simulate no assigned duty
                response = client.get('/duty-teams')
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"You do not have a duty today.", response.data)

    def test_devos_feedback_with_feedback(self):
        
        with patch('routes.sections', ['Minis', 'Micros']), \
         patch('routes.feedback_records', {
             ('2024-12-20', 'Micros'): {"feedback": "Great job!"}
         }):
            response = self.client.get('/devos-feedback?date=2024-12-20')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Great job!", response.data)

    def test_devos_feedback_edit_redirect_not_logged_in(self):
        response = self.client.get('/devos-feedback/edit?date=2024-12-20&section=Minis')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/?next=http://localhost/devos-feedback/edit?date%3D2024-12-20%26section%3DMinis', response.headers['Location'])

    def test_devos_feedback_edit_redirect_missing_params(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_name'] = 'Alice'  # Simulate logged-in user
            response = client.get('/devos-feedback/edit?section=Micros')  # Missing date_str
            self.assertEqual(response.status_code, 302)
            self.assertIn('/', response.headers['Location'])  # Redirects to index

    def test_login_redirects_correctly(self):
        response = self.client.post('/login', data={'user_name': 'User1'})
        self.assertEqual(response.status_code, 302)  # Redirect after login
        self.assertIn('/', response.headers['Location'])

if __name__ == '__main__':
    unittest.main()