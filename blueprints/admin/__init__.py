from flask import Blueprint

bp = Blueprint("admin", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/admin)
from . import routes  # noqa
