from datetime import datetime
from flask import request, session, jsonify
from backend.bcssm_backend.utils import execute_query

import logging
logger = logging.getLogger(__name__)

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
        try:
            # Get date from query param or use today
            date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')

            # Get current user from session
            user_name = session.get('user_name')
            user_info = get_user_info(user_name) if user_name else None
            is_leader = user_info and user_info["role"] in ["Section Leader", "Team Leader", "Admin"]

            # Get feedback records
            daily_feedback, error = get_feedback_by_date(date_str)
            if daily_feedback is None:
                logger.error("Error fetching feedback for date %s: %s", date_str, error)
                return jsonify({"error": "Internal server error"}), 500

            return jsonify({
                "date": date_str,
                "feedback": daily_feedback,
                "user": user_info,
                "is_leader": is_leader
            })
        except Exception as e:
            logger.exception("Unhandled exception in get_devos_feedback_data: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    @app.route('/api/devos-feedback/edit', methods=['POST'])
    def edit_devos_feedback():
        """Edit feedback for a specific date and section."""
        date_str = request.args.get('date')
        section_name = request.args.get('section')
        payload = request.get_json() or {}
        new_feedback = payload.get('feedback')
        editor_id = session.get('user_id')
        print("DEBUG edit_devos_feedback - editor_id:", editor_id)
        if not editor_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Validate input
        if not date_str or not section_name or new_feedback is None:
            return jsonify({'error': 'Missing date, section, or feedback'}), 400

        # Retrieve the section ID
        sec_query = "SELECT id FROM sections WHERE name = :section_name;"
        sec_rows = execute_query(sec_query, {'section_name': section_name})
        if not sec_rows:
            return jsonify({'error': f"Section '{section_name}' not found"}), 400
        section_id = sec_rows[0][0]

        try:
            # Upsert feedback (PostgreSQL syntax)
            upsert_query = """
                INSERT INTO feedback (section_id, date, feedback, last_edited_by, last_edited_at)
                VALUES (:section_id, :date_str, :new_feedback, :editor_id, CURRENT_TIMESTAMP)
                ON CONFLICT (section_id, date) DO UPDATE
                  SET feedback = EXCLUDED.feedback,
                      last_edited_by = EXCLUDED.last_edited_by,
                      last_edited_at = EXCLUDED.last_edited_at;
            """
            execute_query(upsert_query, {
                'section_id': section_id,
                'date_str': date_str,
                'new_feedback': new_feedback,
                'editor_id': editor_id
            })
            return jsonify({'success': True}), 200
        except Exception as e:
            logger.exception("Error editing feedback for date %s, section %s: %s", date_str, section_name, e)
            return jsonify({'error': 'Internal server error'}), 500