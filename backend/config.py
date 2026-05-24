import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fallback_key')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True
    ENV = 'development'
    SESSION_COOKIE_SECURE = False

class TestingConfig(Config):
    TESTING = True
    ENV = 'testing'
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True