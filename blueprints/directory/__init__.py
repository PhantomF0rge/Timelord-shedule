from flask import Blueprint
bp = Blueprint("directory", __name__, template_folder="../../templates", static_folder="../../static")
from . import routes  # noqa
