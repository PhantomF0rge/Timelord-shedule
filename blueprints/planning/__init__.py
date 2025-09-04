from flask import Blueprint

bp = Blueprint("planning", __name__, template_folder="../../templates")

# важно: импортируем роуты, чтобы эндпоинты зарегистрировались
from . import routes  # noqa
