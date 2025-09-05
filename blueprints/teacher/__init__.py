from flask import Blueprint

bp = Blueprint("teacher", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/teacher)
from . import routes  # noqa
