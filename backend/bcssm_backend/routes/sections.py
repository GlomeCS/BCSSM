import logging
from flask import g, jsonify

from backend.bcssm_backend.decorators import require_auth, handle_route_errors
from backend.bcssm_backend.utils import (
    get_all_sections_with_users, get_users_by_section_optimized
)

logger = logging.getLogger(__name__)


def init_users_sections_routes(app):
    @app.route('/api/users/by-section', methods=['GET'])
    @require_auth
    @handle_route_errors
    def get_users_by_section_route():
        logger.info(
            "Fetching users grouped by section for user: %s", g.user_name
        )
        sections_data = get_all_sections_with_users()
        total_users = sum(len(s["users"]) for s in sections_data)
        response = {
            "sections": sections_data,
            "total_users": total_users,
            "total_sections": len(sections_data)
        }
        logger.info(
            "Successfully fetched %d sections with %d total users",
            response["total_sections"],
            response["total_users"]
        )
        return jsonify(response)

    @app.route('/api/users/section/<section_name>', methods=['GET'])
    @require_auth
    @handle_route_errors
    def get_section_users_route(section_name):
        logger.info("Fetching users for section: %s", section_name)
        users = get_users_by_section_optimized(section_name)
        response = {
            "section": section_name,
            "users": users,
            "user_count": len(users)
        }
        return jsonify(response)
