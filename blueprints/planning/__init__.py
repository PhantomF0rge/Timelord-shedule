from flask import Blueprint

bp = Blueprint("planning", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/planning)
from . import routes  # noqa
