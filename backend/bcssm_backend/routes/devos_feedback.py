from datetime import datetime
from flask import g, request, jsonify

from backend.bcssm_backend.constants import ELEVATED_ROLES
from backend.bcssm_backend.decorators import require_auth, require_feedback_edit_permission, handle_route_errors
from backend.bcssm_backend.feedback_queries import get_feedback_by_date, save_devos_feedback
from backend.bcssm_backend.user_queries import get_user_info

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

        user_info = get_user_info(g.user_name)
        if not user_info:
            logger.warning("User info not found for user: %s", g.user_name)
            return jsonify({"error": "Invalid user"}), 400

        daily_feedback = get_feedback_by_date(date_str)

        return jsonify({
            "date": date_str,
            "feedback": daily_feedback,
            "user": user_info,
            "can_edit_all": g.user_role in ELEVATED_ROLES
        })

    @app.route('/api/devos-feedback/edit', methods=['POST'])
    @require_auth
    @require_feedback_edit_permission
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

        if len(new_feedback) > 256:
            return jsonify(
                {'error': 'Feedback must be 256 characters or fewer'}
            ), 400

        logger.debug("edit_devos_feedback - editor_id: %s", g.user_id)
        save_devos_feedback(section_name, date_str, new_feedback, g.user_id)
        return jsonify({'success': True}), 200
