from flask import g, redirect, request, jsonify
from backend.bcssm_backend.decorators import require_auth, handle_route_errors
from backend.bcssm_backend.duty_queries import get_user_duty
from backend.bcssm_backend.user_queries import get_user_info


def init_main_routes(app):

    @app.route('/')
    def index():
        """ React will handle routing; this route serves the app. """
        return app.send_static_file("index.html")

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return redirect('/')

        return redirect('/')

    @app.route('/duty-teams')
    @require_auth
    @handle_route_errors
    def duty_team():
        """Get duty info for a user."""
        user_name = g.user_name

        user_info = get_user_info(user_name)

        if not user_info:
            app.logger.warning("User '%s' not found in database", user_name)
            return jsonify({"error": "Invalid user"}), 400

        duty_data = get_user_duty(user_name)

        if not duty_data or duty_data.get('error'):
            duty_message = "No duty assigned"
            user_role = user_info.get('role')
        else:
            duty_message = duty_data.get('duty', 'No duty assigned')
            user_role = duty_data.get('role')

        return jsonify({
            "user": user_name,
            "duty_message": duty_message,
            "role": user_role
        })
