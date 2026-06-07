import hmac
import os
import logging

import bcrypt
from flask import request, jsonify, session
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from backend.bcssm_backend.exceptions import BaseError, CacheError
from backend.bcssm_backend.utils import (
    clear_user_cache, clear_duty_cache, clear_feedback_cache, clear_all_cache,
    get_cache_status, get_cache_info, _redact_redis_url,
    execute_query, execute_readonly_query,
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
        except (RedisError, CacheError) as e:
            app.logger.error("Cache status check failed: %s", e)
            return jsonify({
                "status": "unhealthy",
                "error": "Cache status check failed",
                "redis_url": _redact_redis_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
            }), 500

    @app.route("/api/admin/cache/info", methods=['GET'])
    def cache_info():
        return jsonify(get_cache_info())

    def _is_authorized_admin():
        """Returns True if the request carries a valid admin credential.

        Accepts either:
        - a logged-in session whose user has role 'Admin' (fast path), or
        - a session with a user_name whose DB role is 'Admin' (handles stale sessions
          created before user_role was added to the session), or
        - a matching X-Admin-Secret header (bootstrap / out-of-band access).
        """
        if session.get('user_role') == 'Admin':
            return True
        user_name = session.get('user_name')
        if user_name:
            try:
                rows = execute_readonly_query(
                    "SELECT role FROM users WHERE name = :name",
                    {'name': user_name},
                    silent=True,
                )
                if rows and rows[0][0] == 'Admin':
                    session['user_role'] = 'Admin'
                    return True
            except SQLAlchemyError:
                pass
        admin_secret = os.getenv('ADMIN_SECRET', '').strip()
        provided = request.headers.get('X-Admin-Secret', '').strip()
        if not admin_secret:
            logger.warning("Admin endpoint called but ADMIN_SECRET env var is not set")
            return False
        if not provided:
            logger.warning("Admin endpoint called with no X-Admin-Secret header")
            return False
        result = hmac.compare_digest(provided, admin_secret)
        if not result:
            logger.warning("Admin endpoint called with incorrect X-Admin-Secret header")
        return result

    @app.route("/api/admin/passwords-status", methods=['GET'])
    def passwords_status():
        if not _is_authorized_admin():
            return jsonify({'error': 'Unauthorized'}), 403
        try:
            rows = execute_readonly_query(
                "SELECT u.name, (u.password_hash IS NOT NULL) AS has_password "
                "FROM users u ORDER BY u.name"
            )
            return jsonify({'users': [{'name': r[0], 'has_password': bool(r[1])} for r in rows]}), 200
        except SQLAlchemyError as e:
            logger.error("Failed to fetch password status: %s", e)
            return jsonify({'error': 'Database error'}), 500

    @app.route("/api/admin/set-password", methods=['POST'])
    def set_password():
        if not _is_authorized_admin():
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.json or {}
        user_name = (data.get('user_name') or '').strip()
        password = data.get('password') or ''
        if not user_name or not password:
            return jsonify({'error': 'user_name and password required'}), 400
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            rows = execute_query(
                "UPDATE users SET password_hash = :hash WHERE name = :name RETURNING id",
                {'hash': password_hash, 'name': user_name}
            )
            if not rows:
                return jsonify({'error': 'User not found'}), 404
            return jsonify({'ok': True, 'user_name': user_name}), 200
        except SQLAlchemyError as e:
            logger.error("Failed to set password for %s: %s", user_name, e)
            return jsonify({'error': 'Database error'}), 500


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
