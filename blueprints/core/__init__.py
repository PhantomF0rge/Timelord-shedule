from flask import Blueprint

bp = Blueprint("core", __name__)

from . import routes  # noqa: E402,F401
