import unittest
from utils import get_all_users, get_user_duty, get_users_by_section
from datetime import datetime

class TestUtils(unittest.TestCase):

    def test_get_all_users(self):
        expected_users = [
            "Alice", "Bob", "Charlie", "David", "Eve", "Frank",
            "Grace", "Hank", "Ivy", "Jack", "Kara", "Liam", "Mona", "Nora"
        ]
        self.assertEqual(get_all_users(), expected_users)

    def test_get_user_duty_valid_user(self):
        today_index = datetime.now().weekday()
        duties = ["Breakfast", "Toilets", "Lunch", "General Clean", "Dinner", "Supper"]
        expected_duty = duties[today_index % len(duties)]

        self.assertEqual(get_user_duty("Alice"), {"user": "Alice", "section": "Minis", "role": "Section Leader"})
        self.assertEqual(get_user_duty("Ivy"), {"user": "Ivy", "section": "Minis", "team": "Duty Team 1", "duty": expected_duty})

    def test_get_user_duty_invalid_user(self):
        self.assertEqual(get_user_duty("Unknown"), {"error": "User not found"})

    def test_get_users_by_section(self):
        expected_minis = [
            {"name": "Alice", "role": "Section Leader"},
            {"name": "Ivy", "role": "Team Member"}
        ]
        self.assertEqual(get_users_by_section("Minis"), expected_minis)

        expected_team_leaders = [
            {"name": "Grace", "role": "Team Leader"},
            {"name": "Hank", "role": "Team Leader"}
        ]
        self.assertEqual(get_users_by_section("Team Leaders"), expected_team_leaders)

if __name__ == '__main__':
    unittest.main()