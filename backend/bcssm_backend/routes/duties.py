from flask import session, jsonify, request
from backend.bcssm_backend.utils import get_todays_duties, get_duty_schedule

def init_duties_routes(app):
    @app.route('/api/duties/today', methods=['GET'])
    def get_duties_today():
        """
        Returns JSON list of today's duties:
          - id (UUID string)
          - name
          - duty_description
          - members (list of user names)
          - is_current_user (bool)
        """
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'User not authenticated'}), 401

        duties = get_todays_duties(user_name)
        return jsonify(duties), 200

    @app.route('/api/duties/schedule', methods=['GET'])
    def get_duty_schedule_route():
        """
        Returns JSON object with 2-week duty schedule starting from July 5th, 2025:
        {
          "schedule": [
            {
              "date": "2025-07-05",
              "day_name": "Saturday",
              "week": "Week A",
              "duties": [
                {
                  "duty_name": "Security",
                  "duty_description": "...",
                  "team_name": "Team Alpha",
                  "team_members": [{"name": "John Doe", "week": "Both"}, ...]
                }
              ]
            },
            ...
          ]
        }
        """
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'User not authenticated'}), 401

        try:
            schedule = get_duty_schedule()
            return jsonify({"schedule": schedule}), 200
        except Exception as e:
            return jsonify({'error': f'Failed to fetch duty schedule: {str(e)}'}), 500