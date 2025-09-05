from flask import Blueprint
bp = Blueprint("constraints", __name__)
from . import routes  # noqa: E402,F401
