from flask import jsonify, request, session
from markupsafe import escape

from backend.globals import cache
from backend.utils import (get_all_users, get_user_duty, get_users_by_section,
                   user_assignments, execute_query)


def init_users_routes(app):

    @app.route('/users-by-section')
    def users_by_section():
        try:
            section_name = request.args.get('section')
            users = get_users_by_section(section_name)
            return jsonify({"users": users}), 200
        except Exception as e:
            app.logger.error(f"Failed to fetch users: {str(e)}")
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/user-duty')
    def user_duty():
        try:
            user_name = request.args.get('user')
            duty_data = get_user_duty(user_name)
            return jsonify(duty_data), 200
        except Exception as e:
            app.logger.error(f"Failed to fetch duty: {str(e)}")
            return jsonify({"error": "An internal error has occurred."}), 500


    @app.route('/select-user', methods=['POST'])
    def select_user():
        user_name = request.json.get('user_name')

        if user_name:
            user_name = escape(user_name)  # Escaping user input

        # Get valid users from cache or database
        valid_users = cache.get('valid_users')
        if not valid_users:
            valid_users = get_all_users()
            cache.set('valid_users', valid_users, timeout=300)  # Cache for 5 minutes

        if user_name not in valid_users:
            print("Invalid user selected")
            return {"message": "Invalid user selected."}, 400

        session['user_name'] = user_name

        # Fetch full user record for ID, role, and section
        user_rows = execute_query(
            "SELECT u.id, u.role, s.name AS section_name "
            "FROM users u "
            "LEFT JOIN sections s ON u.section_id = s.id "
            "WHERE u.name = :user_name",
            {'user_name': user_name}
        )
        if not user_rows:
            return jsonify({'error': 'User record not found'}), 500
        user_row = user_rows[0]
        # Unpack tuple: (id, role, section_name)
        user_id, role, section_name = user_row

        session['user_id'] = user_id
        is_leader = role in ["Section Leader", "Team Leader", "Admin"]
        session['user_section'] = section_name
        session['is_leader'] = is_leader

        # Return JSON including user state
        response = jsonify({
            "message": f"User {escape(user_name)} successfully selected.",
            "is_logged_in": True,
            "user_section": session['user_section'],
            "is_leader": session['is_leader']
        })
        return response, 200

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

    @app.route('/get-users')
    def get_users():
        try:
            # Fetch users from cache or database
            users = cache.get('all_users')
            if not users:
                users = get_all_users()
                cache.set('all_users', users, timeout=300)  # Cache for 5 minutes

            return jsonify({"users": users}), 200
        except Exception as e:
            app.logger.error(f"Failed to fetch users: {str(e)}")
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.context_processor
    def inject_user_state():
        user_name = session.get('user_name', None)
        if user_name:
            return {
                'is_logged_in': True,
                'user_section': session.get('user_section'),
                'is_leader': session.get('is_leader'),
                'user_id': session.get('user_id')
            }
        else:
            return {
                'is_logged_in': False,
                'user_section': None,
                'is_leader': False,
                'user_id': None
            }
        