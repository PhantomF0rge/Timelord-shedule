from flask import Blueprint
bp = Blueprint("schedule", __name__)
from . import routes  # noqa: E402,F401
