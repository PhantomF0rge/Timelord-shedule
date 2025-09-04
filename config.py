import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SAMESITE = "Lax"
    JSON_SORT_KEYS = False
    # Access control / CORS can be added later if needed

class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

class ProdConfig(Config):
    pass
