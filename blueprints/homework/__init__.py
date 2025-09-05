from flask import Blueprint

bp = Blueprint("homework", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/homework)
from . import routes  # noqa
