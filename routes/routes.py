from urllib.parse import urlparse

from flask import redirect, render_template, request, session, url_for
from markupsafe import escape
from utils import get_all_users, get_user_duty, user_assignments


def init_main_routes(app):

    @app.route('/')
    def index():
        users = get_all_users()  # Fetch all users to populate the dropdown
        next_url = request.args.get('next', '/')
        return render_template('index.html', users=users, next = next_url)
            
    @app.route('/login', methods=['POST'])
    def login():
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
            return redirect('/', code=302)
        print("User not found, redirecting to index")  # Debug log
        return redirect(url_for('index'))

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