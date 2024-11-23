# routes.py
from flask import render_template, request, jsonify
from datetime import datetime
from utils import get_user_duty, get_users_by_section  # Assuming you move the duty fetching logic to utils.py

def init_routes(app):

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/duty-teams')
    def duty_team():
        return render_template('duty_teams.html')

    @app.route('/users-by-section')
    def users_by_section():
        section = request.args.get('section')
        users = get_users_by_section(section)  # A function in utils.py
        return jsonify({"users": users})

    @app.route('/user-duty')
    def user_duty():
        user_name = request.args.get('user')
        duty_data = get_user_duty(user_name)  # Another function in utils.py
        return jsonify(duty_data)