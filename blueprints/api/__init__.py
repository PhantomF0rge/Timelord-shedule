from flask import Blueprint

# Не задаём url_prefix здесь, он задаётся в app.register_blueprint(..., url_prefix="/api/v1")
bp = Blueprint("api", __name__)

# важно: подтянуть маршруты при импорте блюпринта
from . import routes  # noqa: E402,F401
