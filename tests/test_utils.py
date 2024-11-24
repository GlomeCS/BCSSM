import unittest
from utils import get_all_users, get_user_duty

class TestUtils(unittest.TestCase):

    def test_get_all_users(self):
        expected_users = [
            "Alice", "Bob", "Charlie", "David", "Eve", "Frank",
            "Grace", "Hank", "Ivy", "Jack", "Kara", "Liam", "Mona", "Nora"
        ]
        self.assertEqual(get_all_users(), expected_users)

    def test_get_user_duty_valid_user(self):
        self.assertEqual(get_user_duty("Alice"), {"user": "Alice", "section": "Minis", "role": "Section Leader"})
        self.assertEqual(get_user_duty("Ivy"), {"user": "Ivy", "section": "Minis", "team": "Duty Team 1", "duty": "Breakfast"})

    def test_get_user_duty_invalid_user(self):
        self.assertEqual(get_user_duty("Unknown"), {"error": "User not found"})

if __name__ == '__main__':
    unittest.main()