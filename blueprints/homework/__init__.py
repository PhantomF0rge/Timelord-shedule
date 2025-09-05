from flask import Blueprint
bp = Blueprint("homework", __name__)
from . import routes  # noqa: E402,F401
