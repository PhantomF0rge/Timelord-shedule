from flask import Blueprint
bp = Blueprint("schedule", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("schedule_api", __name__)
from . import routes  # noqa
