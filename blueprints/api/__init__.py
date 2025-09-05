from flask import Blueprint

bp = Blueprint("api", __name__)

# ВАЖНО: импортируем роуты, чтобы endpoint'ы реально зарегистрировались.
# Код в routes.py написан так, чтобы НЕ падать при импорте (мягкие импорты моделей).
from . import routes  # noqa: E402,F401
