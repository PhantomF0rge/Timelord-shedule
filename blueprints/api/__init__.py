from flask import Blueprint

bp = Blueprint("api", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/api)
from . import routes  # noqa
