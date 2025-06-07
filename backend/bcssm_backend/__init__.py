import logging
import os

from dotenv import load_dotenv
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

from backend.config import DevelopmentConfig, ProductionConfig, TestingConfig
from backend.globals import cache, db
from backend.bcssm_backend.routes.routes import init_main_routes
from backend.bcssm_backend.routes.users import init_users_routes
from backend.bcssm_backend.routes.devos_feedback import init_feedback_routes
from backend.bcssm_backend.routes.duties import init_duties_routes

from backend.bcssm_backend.utils import get_all_sections

def create_app():
    load_dotenv()

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    CORS(app)
    
    # Configure the app based on the environment
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'development':
        app.config.from_object(DevelopmentConfig)
    elif env == 'testing':
        app.config.from_object(TestingConfig)
    elif env == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    USER = os.getenv("user")
    PASSWORD = os.getenv("password")
    HOST = os.getenv("host")
    PORT = os.getenv("port", "5432")  # Default to 5432 if not set
    DBNAME = os.getenv("database")

    if not all([USER, PASSWORD, HOST, DBNAME]):
        raise RuntimeError("Missing required database environment variables.")

    connection_url = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}"
    app.config['SQLALCHEMY_DATABASE_URI'] = connection_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configure SQLAlchemy engine connection pooling
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', 10)),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 20)),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', 30)),
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 1800)),
        'pool_pre_ping': True,
    }
    
    # Prevent DB initialization during testing
    if not app.config.get("TESTING"):
        db.init_app(app)
    
    cache.init_app(app)

    init_main_routes(app)
    init_users_routes(app)
    init_feedback_routes(app)
    init_duties_routes(app)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    configure_logging(app)

    # Expose section list for React frontend
    @app.route("/api/sections")
    @cache.cached(timeout=3600)  # cache for 1 hour
    def api_sections():
        """Return list of section names in configured display order."""
        sections = get_all_sections()
        return jsonify(sections)

    # Serve React Frontend
    # Update your serve_react function in app.py
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_react(path):
        """ Serve React index.html for all unknown routes (supports React Router) """
        app.logger.info("React route fallback triggered for path: %s", path)
        
        # For API routes, pass through to other handlers
        if path.startswith(('api/', 'get-', 'select-', 'devos-', 'duty-')):
            return app.send_static_file('index.html')
        
        # Sanitize input path to prevent directory traversal
        safe_path = os.path.normpath(path)
        # Strip any leading slashes or backslashes
        safe_path = safe_path.lstrip("/\\")
        # If the normalized path attempts to go above the static folder, reset to empty
        if safe_path.startswith(".."):
            safe_path = ""
        # Construct the full requested path
        requested_path = os.path.join(app.static_folder, safe_path)
        # Normalize the full requested path
        requested_path = os.path.normpath(requested_path)
        # Ensure the requested path is confined to the static folder
        if not requested_path.startswith(app.static_folder + os.sep):
            app.logger.warning("Path traversal attempt detected: %s", path)
            safe_path = "index.html"
            requested_path = os.path.join(app.static_folder, safe_path)
        if os.path.isfile(requested_path):
            return send_from_directory(app.static_folder, safe_path)
        
        # For all other routes, serve the index.html file to support React Router
        app.logger.info("React serving index.html for path: /%s", path)
        return send_from_directory(app.static_folder, "index.html")


    return app

def configure_logging(app=None):
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    if app:
        app.logger.setLevel(logging.DEBUG)

if __name__ == "__main__":
    app = create_app()    
    # Enable debug mode only in development environment
    debug_mode = os.getenv("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=8080, debug=debug_mode)