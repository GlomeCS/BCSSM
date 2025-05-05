from datetime import datetime
from flask import redirect, render_template, request, session, url_for, flash, jsonify
from backend.utils import execute_query

def get_feedback_by_date(date_str):
    """Fetch feedback from the database for a given date."""
    query = """
    SELECT s.name AS section_name, f.feedback
    FROM sections s
    LEFT JOIN feedback f ON s.id = f.section_id AND f.date = :date;
    """
    try:
        feedback_rows = execute_query(query, {"date": date_str})
        daily_feedback = {row[0]: row[1] if row[1] is not None else "No feedback available" for row in feedback_rows}
        return daily_feedback, None  # Always return two values
    except Exception as e:
        return None, str(e)  # Return None for feedback, and an error message


def get_user_info(user_name):
    """Fetch user role and section for permission checking."""
    user_info_query = """
    SELECT u.name, u.role, s.name AS section_name
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    WHERE u.name = :user_name;
    """
    try:
        user_rows = execute_query(user_info_query, {"user_name": user_name})
        if user_rows:
            return {
                "name": user_rows[0][0],
                "role": user_rows[0][1],
                "section": user_rows[0][2],
            }
        return None  # User not found
    except Exception:
        return None  # Handle errors gracefully


def init_feedback_routes(app):
    @app.route('/api/devos-feedback', methods=['GET'])
    def get_devos_feedback_data():
        # Get date from query param or use today
        date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')

        # Get current user from session
        user_name = session.get('user_name')
        user_info = get_user_info(user_name) if user_name else None
        is_leader = user_info and user_info["role"] in ["Section Leader", "Team Leader", "Admin"]

        # Get feedback records
        daily_feedback, error = get_feedback_by_date(date_str)
        if daily_feedback is None:
            return jsonify({"error": error}), 500

        return jsonify({
            "date": date_str,
            "feedback": daily_feedback,
            "user": user_info,
            "is_leader": is_leader
        })