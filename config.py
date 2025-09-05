from __future__ import annotations
import os
from pathlib import Path

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    BASE_DIR = Path(__file__).resolve().parent
    # SQLite file in project directory
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevConfig(BaseConfig):
    DEBUG = True
    DEBUG = True
    SEED_TEST_DATA = True
    DEFAULT_USERS = [
        {"email": "admin@example.com", "password": "pass", "role": "ADMIN"},
        {"email": "t1@example.com",    "password": "pass", "role": "TEACHER",
         # опционально привязать к существующему Teacher по ФИО
         "teacher_full_name": None}
    ]

class ProdConfig(BaseConfig):
    DEBUG = False
    JSON_SORT_KEYS = False
    SEED_TEST_DATA = False
    DEFAULT_USERS = []

config_map = {
    "dev": DevConfig,
    "prod": ProdConfig,
    "default": DevConfig,
}

HOMEWORK_ALLOW_PAST = False         # запрещать ДЗ для уже прошедших занятий
HOMEWORK_ADMIN_OVERRIDE = True      # админу можно всегда