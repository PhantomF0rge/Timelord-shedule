from flask import Blueprint

bp = Blueprint("constraints", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/constraints)
from . import routes  # noqa
