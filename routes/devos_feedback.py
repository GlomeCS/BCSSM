from flask import render_template, request, session, redirect, url_for
from datetime import datetime
from utils import user_assignments, feedback_records, sections

def init_feedback_routes(app):

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
                return redirect(url_for('index', next=request.url))
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