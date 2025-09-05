from flask import Blueprint
bp = Blueprint("reports", __name__, template_folder="../../templates", static_folder="../../static")
from . import routes  # noqa
