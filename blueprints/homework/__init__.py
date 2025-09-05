from flask import Blueprint
bp = Blueprint("homework", __name__, template_folder="../../templates", static_folder="../../static")
from . import routes  # noqa
