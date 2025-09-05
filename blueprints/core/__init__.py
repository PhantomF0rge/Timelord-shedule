from flask import Blueprint

bp = Blueprint(
    "core",
    __name__,
    template_folder="../../templates",
    static_folder="../../static",
)
api_bp = Blueprint("core_api", __name__) 
# Критично: импортируем функции, чтобы регистрировались маршруты
from . import routes  # noqa: E402,F401