import os

from flask import jsonify, send_from_directory
from redis.exceptions import RedisError

from backend.bcssm_backend.utils import get_all_sections, get_health_status


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
            return jsonify(get_health_status())
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
        static_root = os.path.realpath(app.static_folder)
        requested_path = os.path.realpath(os.path.join(static_root, safe_path))
        if os.path.commonpath([requested_path, static_root]) != static_root:
            app.logger.warning("Attempted directory traversal detected: %s", path)
            return send_from_directory(app.static_folder, "index.html")
        if os.path.isfile(requested_path):
            return send_from_directory(
                app.static_folder,
                os.path.relpath(requested_path, app.static_folder)
            )

        app.logger.info("React serving index.html for path: /%s", path)
        return send_from_directory(app.static_folder, "index.html")
