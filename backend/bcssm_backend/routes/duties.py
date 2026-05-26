import logging

from flask import jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend.utils import get_duty_schedule, get_todays_duties
from backend.bcssm_backend.auth import get_username_from_request

logger = logging.getLogger(__name__)


def init_duties_routes(app):
    @app.route('/api/duties/today', methods=['GET'])
    def get_duties_today():
        """
        Returns JSON list of today's duties:
          - id (UUID string)
          - name
          - duty_description
          - team_name
          - members (list of user names)
          - is_current_user (bool)
        """
        user_name = get_username_from_request()
        if not user_name:
            logger.warning("No username found in request for /api/duties/today")
            return jsonify({'error': 'Username required'}), 400

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
    def get_duty_schedule_route():
        """
        Returns JSON object with 2-week duty schedule starting from July 4th, 2026:
        {
          "schedule": [
            {
              "date": "2026-07-04",
              "day_name": "Saturday",
              "week": "Week A",
              "duties": [
                {
                  "duty_name": "Security",
                  "duty_description": "...",
                  "team_name": "Team Alpha",
                  "team_members": [{"name": "John Doe", "week": "Both"}, ...]
                }
              ]
            },
            ...
          ]
        }
        """
        user_name = get_username_from_request()
        if not user_name:
            logger.warning("No username found in request for /api/duties/schedule")
            return jsonify({'error': 'Username required'}), 400

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