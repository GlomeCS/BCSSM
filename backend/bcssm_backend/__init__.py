import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from backend.config import DevelopmentConfig, ProductionConfig, TestingConfig
from backend.globals import cache, db
from backend.bcssm_backend.routes.routes import init_main_routes
from backend.bcssm_backend.routes.users import init_users_routes
from backend.bcssm_backend.routes.devos_feedback import init_feedback_routes
from backend.bcssm_backend.routes.duties import init_duties_routes
from backend.bcssm_backend.routes.sections import init_users_sections_routes
from backend.bcssm_backend.routes.admin import init_admin_routes, register_error_handlers
from backend.bcssm_backend.routes.system import init_system_routes


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
    init_main_routes(app)
    init_users_routes(app)
    init_feedback_routes(app)
    init_duties_routes(app)
    init_users_sections_routes(app)
    init_admin_routes(app)
    init_system_routes(app)


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

    # Register error handlers
    register_error_handlers(app)

    # Teardown and logging
    @app.teardown_appcontext
    def shutdown_session(exception):
        if not app.config.get("TESTING"):
            db.session.remove()

    configure_logging(app)

    return app

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
