import os
import psycopg2
import logging
from flask import Flask
from routes.routes import init_main_routes
from routes.devos_feedback import init_feedback_routes
from routes.users import init_users_routes
from config import DevelopmentConfig, TestingConfig, ProductionConfig
from dotenv import load_dotenv
from globals import db, cache

def create_app():
    load_dotenv()

    app = Flask(__name__)
    
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
    app.config['SQLALCHEMY_DATABASE_URI'] = (connection_url)

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    cache.init_app(app)

    init_main_routes(app)
    init_feedback_routes(app)
    init_users_routes(app)

    configure_logging(app)

    return app

def configure_logging(app=None):
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    if app:
        app.logger.setLevel(logging.DEBUG)