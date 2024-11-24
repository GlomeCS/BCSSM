from flask import render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from utils import get_user_duty, get_users_by_section, user_assignments, get_all_users

def init_routes(app):

    @app.route('/')
    def index():
        users = get_all_users()  # Fetch all users to populate the dropdown
        return render_template('index.html', users=users)

    @app.route('/duty-teams')
    def duty_team():
        user_name = session.get('user_name')
        if not user_name:
            return redirect(url_for('index'))  # Redirect to index if no user is selected

        # Get duty data for the user
        duty_data = get_user_duty(user_name)

        # Check if the user is a team leader and doesn't have a duty
        if not duty_data:
            duty_message = "You do not have a duty today."
        else:
            duty_message = duty_data.get('duty', 'No duty assigned')  # This depends on your duty data structure

        return render_template('duty_teams.html', user=user_name, duty_message=duty_message)

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

    @app.route('/devos-feedback')
    def devos_feedback():
        return render_template('devos_feedback.html')  # Placeholder for future feedback page