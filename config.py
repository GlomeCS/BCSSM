class Config:
    SECRET_KEY = 'your_secret_key'
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