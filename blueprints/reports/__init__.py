from flask import Blueprint

bp = Blueprint("reports", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/reports)
from . import routes  # noqa
