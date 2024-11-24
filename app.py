import os
from flask import Flask
from routes import init_routes
from config import DevelopmentConfig, TestingConfig, ProductionConfig

app = Flask(__name__)

# Dynamically load configuration based on environment
env = os.getenv('FLASK_ENV', 'development')  # Default to 'development'

if env == 'development':
    app.config.from_object(DevelopmentConfig)
elif env == 'testing':
    app.config.from_object(TestingConfig)
else:
    app.config.from_object(ProductionConfig)

# Initialize routes
init_routes(app)

if __name__ == "__main__":
    app.run()