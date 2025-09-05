from flask import Blueprint

bp = Blueprint("directory", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/directory)
from . import routes  # noqa
