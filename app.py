import os
from flask import Flask
from routes.routes import init_main_routes
from routes.devos_feedback import init_feedback_routes
from routes.users import init_users_routes
from config import DevelopmentConfig, TestingConfig, ProductionConfig
from dotenv import load_dotenv
load_dotenv()

def create_app():
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
    
    # Initialize routes or extensions here if needed
    init_main_routes(app)
    init_feedback_routes(app)
    init_users_routes(app)
    return app