import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-secret-change-in-production')

class TestingConfig(Config):
    TESTING = True
    SESSION_COOKIE_SECURE = False
    SECRET_KEY = 'testing-only-secret'

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() != 'false'
