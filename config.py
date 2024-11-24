class Config:
    SECRET_KEY = 'your-secret-key'  # Replace with a secure, random key
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True


class ProductionConfig(Config):
    SECRET_KEY = 'your-production-secret-key'  # Replace with a secure, random key