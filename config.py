from __future__ import annotations
import os
from pathlib import Path

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    BASE_DIR = Path(__file__).resolve().parent
    # SQLite file in project directory
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

class DevConfig(BaseConfig):
    DEBUG = True

class ProdConfig(BaseConfig):
    DEBUG = False

config_map = {
    "dev": DevConfig,
    "prod": ProdConfig,
    "default": DevConfig,
}

HOMEWORK_ALLOW_PAST = False         # запрещать ДЗ для уже прошедших занятий
HOMEWORK_ADMIN_OVERRIDE = True      # админу можно всегда