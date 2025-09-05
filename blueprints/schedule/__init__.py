from flask import Blueprint

bp = Blueprint("schedule", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/schedule)
from . import routes  # noqa
