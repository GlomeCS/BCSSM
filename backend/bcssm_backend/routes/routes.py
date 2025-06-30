from urllib.parse import urlparse

from flask import redirect, request, session, jsonify
from markupsafe import escape
from backend.bcssm_backend.utils import get_user_duty, user_assignments


def init_main_routes(app):

    @app.route('/')
    def index():
        """ React will handle routing; this route serves the app. """
        return app.send_static_file("index.html")
            
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            # For GET requests, simply redirect to the homepage
            return redirect('/')

        # Handle POST request for user login:
        user_name = request.form.get('user_name')
        user_name = escape(user_name)  # Escape to prevent XSS
        print(f"Received user_name: {user_name}")  # Debug log
        
        if user_name in user_assignments:
            session['user_name'] = user_name
            target = request.args.get('target', '/').strip()  # Default to '/' if target is empty
            target = target.replace('\\', '')  # Remove backslashes
            print(f"Processed target: {target}")  # Debug log
            if not urlparse(target).netloc and not urlparse(target).scheme:
                print(f"Redirecting to: {target}")  # Debug log
                return redirect(target, code=302)
            print("Target invalid, redirecting to '/'")  # Debug log
            return redirect('/')
        print("User not found, redirecting to index")  # Debug log
        return redirect('/')

    @app.route('/duty-teams')
    def duty_team():
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({"error": "User not logged in"}), 401

        # Get duty data for the user
        duty_data = get_user_duty(user_name)

        # Check if the user is a team leader and doesn't have a duty
        if not duty_data or duty_data.get('error'):
            duty_message = "No duty assigned"
            user_role = None
        else:
            duty_message = duty_data.get('duty', 'No duty assigned')
            user_role = duty_data.get('role')

        return jsonify({
            "user": user_name, 
            "duty_message": duty_message,
            "role": user_role
        })