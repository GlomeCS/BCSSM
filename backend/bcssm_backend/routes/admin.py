import os
import logging

from flask import request, jsonify
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from backend.bcssm_backend.exceptions import BaseError
from backend.bcssm_backend.utils import (
    clear_user_cache, clear_duty_cache, clear_feedback_cache, clear_all_cache,
    get_cache_status, get_cache_info, _redact_redis_url,
)

logger = logging.getLogger(__name__)


def init_admin_routes(app):
    @app.route("/api/admin/cache/clear", methods=['POST'])
    def clear_cache_endpoint():
        try:
            data = request.get_json() if request.is_json else {}
            cache_type = data.get('type', 'all')

            if cache_type == 'users':
                clear_user_cache()
                message = "Cleared user-related caches"
            elif cache_type == 'duties':
                clear_duty_cache()
                message = "Cleared duty-related caches"
            elif cache_type == 'feedback':
                clear_feedback_cache()
                message = "Cleared feedback caches"
            elif cache_type == 'all':
                clear_all_cache()
                message = "Cleared all caches"
            else:
                return jsonify({
                    "success": False,
                    "error": "Invalid cache type. Use: users, duties, feedback, or all"
                }), 400

            return jsonify({"success": True, "message": message, "cache_type": cache_type})

        except RedisError as e:
            app.logger.error("Cache clearing failed: %s", e)
            return jsonify({"success": False, "error": "Cache clearing failed"}), 500

    @app.route("/api/admin/cache/status", methods=['GET'])
    def cache_status():
        try:
            return jsonify(get_cache_status())
        except RedisError as e:
            app.logger.error("Cache status check failed: %s", e)
            return jsonify({
                "status": "unhealthy",
                "error": "Cache status check failed",
                "redis_url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
            }), 500

    @app.route("/api/admin/cache/info", methods=['GET'])
    def cache_info():
        return jsonify(get_cache_info())


def register_error_handlers(app):
    @app.errorhandler(BaseError)
    def handle_bcssm_error(e):
        app.logger.error("Application error: %s", e.message)
        return jsonify({"error": e.message}), e.status_code

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        app.logger.error("Unhandled database error: %s", e)
        return jsonify({"error": "A database error occurred"}), 500

    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Resource not found"}), 404
        return e

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        app.logger.error("Unhandled exception: %s", e)
        return jsonify({"error": "Internal server error"}), 500
