from datetime import datetime
from flask import g, request, jsonify

from backend.bcssm_backend.decorators import require_auth, handle_route_errors
from backend.bcssm_backend.utils import (
    get_feedback_by_date, get_user_info, save_devos_feedback
)

import logging
logger = logging.getLogger(__name__)


def init_feedback_routes(app):
    @app.route('/api/devos-feedback', methods=['GET'])
    @require_auth
    @handle_route_errors
    def get_devos_feedback_data():
        date_str = (
            request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
        )
        user_name = g.user_name

        user_info = get_user_info(user_name)
        if not user_info:
            logger.warning("User info not found for user: %s", user_name)
            return jsonify({"error": "Invalid user"}), 400

        EDIT_ROLES = ["Section Leader", "Team Leader", "Admin"]
        can_edit_all = user_info["role"] in EDIT_ROLES

        daily_feedback = get_feedback_by_date(date_str)

        return jsonify({
            "date": date_str,
            "feedback": daily_feedback,
            "user": user_info,
            "can_edit_all": can_edit_all
        })

    @app.route('/api/devos-feedback/edit', methods=['POST'])
    @require_auth
    @handle_route_errors
    def edit_devos_feedback():
        date_str = request.args.get('date')
        section_name = request.args.get('section')
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({'error': 'Request body must be a JSON object'}), 400
        new_feedback = payload.get('feedback')

        if not date_str or not section_name or new_feedback is None:
            return jsonify(
                {'error': 'Missing date, section, or feedback'}
            ), 400

        if not isinstance(new_feedback, str):
            return jsonify({'error': 'Feedback must be a string'}), 400

        if len(new_feedback) > 140:
            return jsonify(
                {'error': 'Feedback must be 140 characters or fewer'}
            ), 400

        editor_id = g.user_id
        editor_name = g.user_name
        logger.debug("edit_devos_feedback - editor_id: %s", editor_id)

        editor_info = get_user_info(editor_name)

        if not editor_info:
            return jsonify({'error': 'Invalid user'}), 400

        LEADER_ROLES = {"Section Leader", "Team Leader", "Admin"}
        can_edit_all = editor_info.get("role") in LEADER_ROLES
        if not can_edit_all and editor_info.get("section") != section_name:
            logger.warning(
                "User %s (section=%s, role=%s) attempted to edit "
                "feedback for section %s",
                editor_info.get("name"), editor_info.get("section"),
                editor_info.get("role"), section_name
            )
            return jsonify({'error': 'Forbidden'}), 403

        save_devos_feedback(section_name, date_str, new_feedback, editor_id)
        return jsonify({'success': True}), 200
