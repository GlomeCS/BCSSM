import logging
import os

from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS

from backend.config import DevelopmentConfig, ProductionConfig, TestingConfig
from backend.globals import cache, db
from backend.routes.devos_feedback import init_feedback_routes
from backend.routes.routes import init_main_routes
from backend.routes.users import init_users_routes

def create_app():
    load_dotenv()

    app = Flask(__name__, static_folder="static", static_url_path="/")
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
    
    # Prevent DB initialization during testing
    if not app.config.get("TESTING"):
        db.init_app(app)
    
    cache.init_app(app)

    init_main_routes(app)
    init_feedback_routes(app)
    init_users_routes(app)

    configure_logging(app)

    # Serve React Frontend
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_react(path):
        """ Serve React index.html for all unknown routes (supports React Router) """
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        app.logger.info(f"React serving index.html for path: /{path}")
        return send_from_directory(app.static_folder, "index.html")

    return app

def configure_logging(app=None):
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    if app:
        app.logger.setLevel(logging.DEBUG)

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=True)