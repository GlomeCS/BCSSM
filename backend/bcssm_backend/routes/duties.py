import logging

from flask import g, jsonify
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend.decorators import require_auth
from backend.bcssm_backend.utils import get_duty_schedule, get_todays_duties

logger = logging.getLogger(__name__)


def init_duties_routes(app):
    @app.route('/api/duties/today', methods=['GET'])
    @require_auth
    def get_duties_today():
        user_name = g.user_name
        try:
            duties = get_todays_duties(user_name)
            logger.info("Retrieved %d duties for user %s", len(duties), user_name)
            return jsonify(duties), 200
        except SQLAlchemyError as e:
            logger.error("Error fetching today's duties for user %s: %s", user_name, e)
            return jsonify({'error': "Failed to fetch today's duties"}), 500
        except Exception as e:
            logger.error("Unexpected error fetching today's duties for user %s: %s", user_name, e)
            return jsonify({'error': "Failed to fetch today's duties"}), 500

    @app.route('/api/duties/schedule', methods=['GET'])
    @require_auth
    def get_duty_schedule_route():
        user_name = g.user_name
        try:
            schedule = get_duty_schedule()
            logger.info("Retrieved duty schedule for user %s", user_name)
            return jsonify({"schedule": schedule}), 200
        except SQLAlchemyError as e:
            logger.error("Error fetching duty schedule for user %s: %s", user_name, e)
            return jsonify({'error': 'Failed to fetch duty schedule'}), 500
        except Exception as e:
            logger.error("Unexpected error fetching duty schedule for user %s: %s", user_name, e)
            return jsonify({'error': 'Failed to fetch duty schedule'}), 500