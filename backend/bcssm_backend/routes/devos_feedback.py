from datetime import datetime
from flask import request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from backend.bcssm_backend.utils import get_feedback_by_date, get_user_info, save_devos_feedback
from backend.bcssm_backend.auth import get_username_from_request, get_user_id_from_request

import logging
logger = logging.getLogger(__name__)


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
        
        try:
            editor_id = get_user_id_from_request()
        except SQLAlchemyError as e:
            logger.error("Failed to resolve editor id: %s", e)
            return jsonify({'error': 'Internal server error'}), 500
        logger.debug("edit_devos_feedback - editor_id: %s", editor_id)

        if not editor_id:
            logger.warning("No user ID found in request for /api/devos-feedback/edit")
            return jsonify({'error': 'Invalid user'}), 400

        # Validate input
        if not date_str or not section_name or new_feedback is None:
            return jsonify({'error': 'Missing date, section, or feedback'}), 400

        try:
            save_devos_feedback(section_name, date_str, new_feedback, editor_id)
            return jsonify({'success': True}), 200
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except SQLAlchemyError as e:
            logger.exception("Error editing feedback for date %s, section %s: %s", date_str, section_name, e)
            return jsonify({'error': 'Internal server error'}), 500