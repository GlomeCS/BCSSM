# backend/routes/duties.py

from flask import session, jsonify
from backend.bcssm_backend.utils import get_todays_duties

def init_duties_routes(app):
    @app.route('/api/duties/today', methods=['GET'])
    def get_duties_today():
        """
        Returns JSON list of today’s duties:
          - id (UUID string)
          - name
          - duty_description
          - members (list of user names)
          - is_current_user (bool)
        """
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'User not authenticated'}), 401

        # Optional: allow overriding “today” via query param ?date=YYYY-MM-DD
        # date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
        # (and pass date_str into your util if you update it)

        duties = get_todays_duties(user_name)
        return jsonify(duties), 200