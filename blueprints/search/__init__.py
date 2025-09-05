from flask import Blueprint

bp = Blueprint("search", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/search)
from . import routes  # noqa
