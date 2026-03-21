"""
Improved app.py with better cache integration
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS

from backend.config import DevelopmentConfig, ProductionConfig, TestingConfig
from backend.globals import cache, db
from backend.bcssm_backend.routes.routes import init_main_routes
from backend.bcssm_backend.routes.users import init_users_routes
from backend.bcssm_backend.routes.devos_feedback import init_feedback_routes
from backend.bcssm_backend.routes.duties import init_duties_routes
from backend.bcssm_backend.routes.sections import (
    init_users_sections_routes
)

from redis.exceptions import RedisError

from backend.bcssm_backend.utils import (
    get_all_sections, clear_user_cache, clear_duty_cache,
    clear_feedback_cache, clear_all_cache
)


def _configure_database(app):
    """Configure database settings for the Flask app."""
    db_user = os.getenv("user")
    db_password = os.getenv("password")
    db_host = os.getenv("host")
    db_port = os.getenv("port", "5432")
    db_name = os.getenv("database")

    if not all([db_user, db_password, db_host, db_name]):
        raise RuntimeError("Missing required database environment variables.")

    connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    app.config['SQLALCHEMY_DATABASE_URI'] = connection_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', '3')),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '7')),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '1800')),
        'pool_pre_ping': True,
    }


def _setup_routes(app):
    """Set up all application routes."""
    # Route initialization
    init_main_routes(app)
    init_users_routes(app)
    init_feedback_routes(app)
    init_duties_routes(app)
    init_users_sections_routes(app)

    # Add cache management routes
    add_cache_management_routes(app)

    # Sections endpoint
    @app.route("/api/sections")
    def api_sections():
        """Return list of section names in configured display order."""
        sections = get_all_sections()
        return jsonify(sections)

    # Enhanced health check
    @app.route("/api/health")
    def health_check():
        """Enhanced health check including cache status"""
        try:
            # Test cache
            cache.set('health_test', 'ok', timeout=10)
            cache_status = cache.get('health_test') == 'ok'
            cache.delete('health_test')

            health_info = {
                "status": "healthy",
                "database": "connected",
                "cache": "healthy" if cache_status else "unhealthy",
                "environment": os.getenv('FLASK_ENV', 'development'),
                "redis_url": os.getenv('REDIS_URL', 'redis://localhost:6379')
            }

            # Overall status based on components
            if not cache_status:
                health_info["status"] = "degraded"

            return jsonify(health_info)

        except RedisError as e:
            app.logger.error("Health check failed: %s", e)
            return jsonify({
                "status": "unhealthy",
                "database": "unknown",
                "cache": "unhealthy",
                "error": "Health check failed",
            }), 500

    # React serving route
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_react(path):
        """ Serve React index.html for all unknown routes (supports React Router) """
        app.logger.info("React route fallback triggered for path: %s", path)

        if path.startswith(('api/', 'get-', 'select-', 'devos-', 'duty-')):
            return app.send_static_file('index.html')

        safe_path = os.path.normpath(path).lstrip("/\\")
        requested_path = os.path.join(app.static_folder, safe_path)
        requested_path = os.path.realpath(requested_path)  # Ensure absolute path resolution
        if not requested_path.startswith(os.path.realpath(app.static_folder)):
            app.logger.warning("Attempted directory traversal detected: %s", path)
            return send_from_directory(app.static_folder, "index.html")
        if os.path.isfile(requested_path):
            return send_from_directory(
                app.static_folder,
                os.path.relpath(requested_path, app.static_folder)
            )

        app.logger.info("React serving index.html for path: /%s", path)
        return send_from_directory(app.static_folder, "index.html")


def create_app():
    """Create and configure the Flask application.

    Returns:
        Flask: Configured Flask application instance.
    """
    load_dotenv()

    here = Path(__file__).parent
    static_dir = here / "static"
    app = Flask(
        __name__,
        static_folder=str(static_dir),
        static_url_path="/static"
    )
    CORS(app)

    # Configure Flask app
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'development':
        app.config.from_object(DevelopmentConfig)
    elif env == 'testing':
        app.config.from_object(TestingConfig)
    elif env == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Configure database
    _configure_database(app)

    # Initialize extensions
    if not app.config.get("TESTING"):
        db.init_app(app)
    cache.init_app(app)

    # Set up routes
    _setup_routes(app)

    # Teardown and logging
    @app.teardown_appcontext
    def shutdown_session(exception):
        if not app.config.get("TESTING"):
            db.session.remove()

    configure_logging(app)

    return app

def add_cache_management_routes(app):
    """Add cache management endpoints using utils functions"""

    @app.route("/api/admin/cache/clear", methods=['POST'])
    def clear_cache_endpoint():
        """Clear cache using utils functions with proper error handling"""
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

            return jsonify({
                "success": True,
                "message": message,
                "cache_type": cache_type
            })

        except RedisError as e:
            app.logger.error("Cache clearing failed: %s", e)
            return jsonify({
                "success": False,
                "error": "Cache clearing failed"
            }), 500

    @app.route("/api/admin/cache/status", methods=['GET'])
    def cache_status():
        """Get detailed cache status"""
        try:
            # Test basic cache operations
            test_key = 'status_test'
            cache.set(test_key, 'working', timeout=10)
            test_result = cache.get(test_key)
            cache.delete(test_key)

            status_info = {
                "status": "healthy" if test_result == 'working' else "unhealthy",
                "redis_url": os.getenv('REDIS_URL', 'redis://localhost:6379'),
                "default_timeout": 300,
                "test_result": test_result,
                "cache_type": "RedisCache",
                "available_operations": {
                    "clear_users": "/api/admin/cache/clear (POST with type: users)",
                    "clear_duties": "/api/admin/cache/clear (POST with type: duties)",
                    "clear_feedback": "/api/admin/cache/clear (POST with type: feedback)",
                    "clear_all": "/api/admin/cache/clear (POST with type: all)"
                }
            }

            return jsonify(status_info)

        except RedisError as e:
            app.logger.error("Cache status check failed: %s", e)
            return jsonify({
                "status": "unhealthy",
                "error": "Cache status check failed",
                "redis_url": os.getenv('REDIS_URL', 'redis://localhost:6379')
            }), 500

    @app.route("/api/admin/cache/info", methods=['GET'])
    def cache_info():
        """Get cache configuration info"""
        return jsonify({
            "cache_config": {
                "type": "RedisCache",
                "url": os.getenv('REDIS_URL', 'redis://localhost:6379'),
                "default_timeout": 300
            },
            "cached_functions": {
                "get_all_users": "15 minutes",
                "get_user_duty": "10 minutes",
                "get_todays_duties": "30 minutes",
                "get_duty_schedule": "2 hours",
                "get_all_sections": "1 hour",
                "get_users_by_section": "30 minutes",
                "get_all_feedback_dates": "2 hours"
            },
            "management_endpoints": {
                "status": "GET /api/admin/cache/status",
                "clear": "POST /api/admin/cache/clear",
                "info": "GET /api/admin/cache/info"
            }
        })

def configure_logging(app=None):
    """Configure logging for the application.

    Args:
        app: Flask application instance (optional).
    """
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    if app:
        app.logger.setLevel(logging.DEBUG)

def run_app():
    """Extracted main logic for easier testing"""
    app = create_app()
    debug_mode = os.getenv("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=8080, debug=debug_mode)

if __name__ == "__main__":  # pragma: no cover
    run_app()
