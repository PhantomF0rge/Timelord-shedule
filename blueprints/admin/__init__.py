from flask import Blueprint
bp = Blueprint("admin", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("admin_api", __name__)
from . import routes  # noqa
