import os

from flask import jsonify, send_from_directory
from redis.exceptions import RedisError

from backend.globals import cache
from backend.bcssm_backend.utils import get_all_sections


def init_system_routes(app):
    @app.route("/api/sections")
    def api_sections():
        sections = get_all_sections()
        if isinstance(sections, dict) and "error" in sections:
            app.logger.error("api_sections failed: %s", sections["error"])
            return jsonify({"error": "Failed to fetch sections"}), 500
        return jsonify(sections)

    @app.route("/api/health")
    def health_check():
        try:
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

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_react(path):
        app.logger.info("React route fallback triggered for path: %s", path)

        if path.startswith(('api/', 'get-', 'select-', 'devos-', 'duty-')):
            return app.send_static_file('index.html')

        safe_path = os.path.normpath(path).lstrip("/\\")
        requested_path = os.path.join(app.static_folder, safe_path)
        requested_path = os.path.realpath(requested_path)
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
