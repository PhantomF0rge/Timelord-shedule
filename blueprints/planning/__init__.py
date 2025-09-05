from flask import Blueprint
bp = Blueprint("planning", __name__)
from . import routes  # noqa: E402,F401
