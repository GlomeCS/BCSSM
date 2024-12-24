from flask import request, jsonify, session
from utils import get_user_duty, get_users_by_section, user_assignments

def init_users_routes(app):

    @app.route('/users-by-section')
    def users_by_section():
        section = request.args.get('section')
        users = get_users_by_section(section)
        return jsonify({"users": users})

    @app.route('/user-duty')
    def user_duty():
        user_name = request.args.get('user')
        duty_data = get_user_duty(user_name)
        return jsonify(duty_data)

    @app.route('/select-user', methods=['POST'])
    def select_user():
        user_name = request.json.get('user_name')
        if user_name not in user_assignments:
            return jsonify({"error": "User not found"}), 400

        # Store the selected user in the session
        session['user_name'] = user_name
        return jsonify({"message": f"User {user_name} selected successfully!"})

    @app.route('/get-selected-user')
    def get_selected_user():
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({"user": None})  # No user selected yet
        return jsonify({"user": user_name})

    @app.route('/logout', methods=['POST'])
    def logout():
        session.pop('user_name', None)
        return jsonify({"message": "User logged out successfully!"})

    @app.context_processor
    def inject_user_state():
        user_name = session.get('user_name', None)
        if user_name:
            user_info = user_assignments.get(user_name, {})
            is_leader = user_info.get('role', 'Team Member') in ["Section Leader", "Team Leader"]
            return {
                'is_logged_in': True,
                'user_section': user_info.get('section'),
                'is_leader': is_leader
            }
        else:
            return {
                'is_logged_in': False,
                'user_section': None,
                'is_leader': False
            }