import logging

from flask import g, jsonify

from backend.bcssm_backend.decorators import require_auth, handle_route_errors
from backend.bcssm_backend.utils import get_duty_schedule, get_todays_duties

logger = logging.getLogger(__name__)


def init_duties_routes(app):
    @app.route('/api/duties/today', methods=['GET'])
    @require_auth
    @handle_route_errors
    def get_duties_today():
        user_name = g.user_name
        duties = get_todays_duties(user_name)
        logger.info("Retrieved %d duties for user %s", len(duties), user_name)
        return jsonify(duties), 200

    @app.route('/api/duties/schedule', methods=['GET'])
    @require_auth
    @handle_route_errors
    def get_duty_schedule_route():
        user_name = g.user_name
        schedule = get_duty_schedule()
        logger.info("Retrieved duty schedule for user %s", user_name)
        return jsonify({"schedule": schedule}), 200
