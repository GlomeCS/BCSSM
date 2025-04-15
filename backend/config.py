import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fallback_key')

    # Add other common configurations here

class DevelopmentConfig(Config):
    DEBUG = True
    ENV = 'development'

class TestingConfig(Config):
    TESTING = True
    ENV = 'testing'

class ProductionConfig(Config):
    DEBUG = False
    ENV = 'production'