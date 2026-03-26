from datetime import datetime
from urllib.parse import unquote
from flask import request, session, jsonify
from markupsafe import escape
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend.utils import execute_query

import logging
logger = logging.getLogger(__name__)


def get_username_from_request():
    """Helper function to get username from various request sources"""
    # Try request body first (for POST requests)
    if request.method == 'POST' and request.json:
        username = request.json.get('user_name')
        if username:
            return escape(unquote(username))
    
    # Try query parameters (for GET requests)
    username = request.args.get('user_name') or request.args.get('user')
    if username:
        return escape(unquote(username))
    
    # Try headers (sent by frontend API wrapper)
    username = request.headers.get('X-Current-User')
    if username:
        return escape(unquote(username))
    
    # Fallback to session for backward compatibility
    return session.get('user_name')


def get_user_id_from_request():
    """Helper function to get user_id from various request sources"""
    # First try to get username and look it up
    user_name = get_username_from_request()
    if user_name:
        try:
            user_rows = execute_query(
                "SELECT u.id FROM users u WHERE u.name = :user_name",
                {'user_name': user_name}
            )
            if user_rows:
                return user_rows[0][0]
        except SQLAlchemyError as e:
            logger.error("Error looking up user ID for %s: %s", user_name, e)
    
    # Fallback to session
    return session.get('user_id')


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
    except SQLAlchemyError as e:
        logger.error("Error in get_feedback_by_date for date %s: %s", date_str, e)
        return None, "An error occurred while fetching feedback"


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
    except SQLAlchemyError as e:
        logger.error("Failed to fetch user info for %s: %s", user_name, e)
        return None


def init_feedback_routes(app):
    @app.route('/api/devos-feedback', methods=['GET'])
    def get_devos_feedback_data():
        try:
            # Get date from query param or use today
            date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')

            # Get current user from multiple sources (query param, header, or session)
            user_name = get_username_from_request()
            
            if not user_name:
                logger.warning("No username found in request for /api/devos-feedback")
                return jsonify({"error": "Username required"}), 400

            user_info = get_user_info(user_name)
            if not user_info:
                logger.warning(f"User info not found for user: {user_name}")
                return jsonify({"error": "Invalid user"}), 400
                
            is_leader = user_info["role"] in ["Section Leader", "Team Leader", "Admin"]

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
        except SQLAlchemyError as e:
            logger.exception("Unhandled exception in get_devos_feedback_data: %s", e)
            return jsonify({"error": "Internal server error"}), 500

    @app.route('/api/devos-feedback/edit', methods=['POST'])
    def edit_devos_feedback():
        """Edit feedback for a specific date and section."""
        date_str = request.args.get('date')
        section_name = request.args.get('section')
        payload = request.get_json() or {}
        new_feedback = payload.get('feedback')
        
        # Get editor ID from multiple sources
        editor_id = get_user_id_from_request()
        logger.info(f"DEBUG edit_devos_feedback - editor_id: {editor_id}")
        
        if not editor_id:
            logger.warning("No user ID found in request for /api/devos-feedback/edit")
            return jsonify({'error': 'Username required'}), 400

        # Validate input
        if not date_str or not section_name or new_feedback is None:
            return jsonify({'error': 'Missing date, section, or feedback'}), 400

        # Retrieve the section ID
        sec_query = "SELECT id FROM sections WHERE name = :section_name;"
        try:
            sec_rows = execute_query(sec_query, {'section_name': section_name})
        except SQLAlchemyError as e:
            logger.error("Failed to fetch section '%s': %s", section_name, e)
            return jsonify({'error': 'Internal server error'}), 500
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
        except SQLAlchemyError as e:
            logger.exception("Error editing feedback for date %s, section %s: %s", date_str, section_name, e)
            return jsonify({'error': 'Internal server error'}), 500