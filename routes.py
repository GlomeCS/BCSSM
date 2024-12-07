from flask import render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from utils import get_user_duty, get_users_by_section, user_assignments, get_all_users, feedback_records, sections, get_all_feedback_dates

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

    @app.route('/devos-feedback', methods=['GET'])
    def devos_feedback():
        # Determine date
        date_str = request.args.get('date')
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')

        # Collect feedback for all sections
        daily_feedback = {}
        for section in sections:  # sections is a list like ["Minis", "Micros", "Minors", ...]
            entry = feedback_records.get((date_str, section))
            if entry:
                daily_feedback[section] = entry["feedback"]
            else:
                daily_feedback[section] = None  # No feedback yet

        # Check if user is logged in and their role
        user_name = session.get('user_name', None)
        user_info = user_assignments.get(user_name) if user_name else None
        user_role = user_info.get('role', 'Team Member') if user_info else None
        is_leader = user_role in ["Section Leader", "Team Leader"]

        return render_template('devos_feedback.html',
                               date_str=date_str,
                               daily_feedback=daily_feedback,
                               is_logged_in=(user_name is not None),
                               user_section=(user_info["section"] if user_info else None),
                               is_leader=is_leader)
    
    @app.route('/devos-feedback/edit', methods=['GET', 'POST'])
    def devos_feedback_edit():
        user_name = session.get('user_name')
        if not user_name:
            return redirect(url_for('index'))
        user_info = user_assignments.get(user_name)
        user_role = user_info.get('role', 'Team Member') if user_info else None
        is_leader = user_role in ["Section Leader", "Team Leader"]
    
        date_str = request.args.get('date')
        section = request.args.get('section')
        if not date_str or not section:
            return redirect(url_for('devos_feedback'))
    
        # Check permission
        if not is_leader and user_info["section"] != section:
            return "Not authorized", 403
    
        if request.method == 'POST':
            feedback_text = request.form.get('feedback')
            feedback_records[(date_str, section)] = {
                "feedback": feedback_text,
                "last_edited_by": user_name,
                "last_edited_at": datetime.now()
            }
            return redirect(url_for('devos_feedback', date=date_str))
        
        # GET: show current feedback if any
        entry = feedback_records.get((date_str, section), None)
        existing_text = entry["feedback"] if entry else ""
        return render_template('devos_feedback_edit.html', date_str=date_str, section=section, feedback_text=existing_text)
    

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