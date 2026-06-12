from urllib.parse import urlparse
from flask import g, redirect, request, session, jsonify
from markupsafe import escape
from backend.bcssm_backend.decorators import require_auth, handle_route_errors
from backend.bcssm_backend.utils import get_user_duty, user_assignments, execute_query


def init_main_routes(app):

    @app.route('/')
    def index():
        """ React will handle routing; this route serves the app. """
        return app.send_static_file("index.html")

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return redirect('/')

        user_name = request.form.get('user_name')
        user_name = escape(user_name)  # Escape to prevent XSS
        app.logger.debug("Received user_name: %s", user_name)

        if user_name in user_assignments:
            session['user_name'] = user_name
            target = request.args.get('target', '/').strip()
            target = target.replace('\\', '')
            app.logger.debug("Processed target: %s", target)
            if not urlparse(target).netloc and not urlparse(target).scheme:
                app.logger.debug("Redirecting to: %s", target)
                return redirect(target, code=302)
            app.logger.debug("Target invalid, redirecting to '/'")
            return redirect('/')
        app.logger.debug("User not found, redirecting to index")
        return redirect('/')

    @app.route('/duty-teams')
    @require_auth
    @handle_route_errors
    def duty_team():
        """Get duty info for a user."""
        user_name = g.user_name

        user_rows = execute_query(
            "SELECT u.id, u.name, u.role FROM users u WHERE u.name = :user_name",
            {'user_name': user_name}
        )

        if not user_rows:
            app.logger.warning("User '%s' not found in database", user_name)
            return jsonify({"error": "Invalid user"}), 400

        duty_data = get_user_duty(user_name)

        if not duty_data or duty_data.get('error'):
            duty_message = "No duty assigned"
            user_role = user_rows[0][2] if len(user_rows[0]) > 2 else None
        else:
            duty_message = duty_data.get('duty', 'No duty assigned')
            user_role = duty_data.get('role')

        return jsonify({
            "user": user_name,
            "duty_message": duty_message,
            "role": user_role
        })
