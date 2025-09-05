from flask import Blueprint

bp = Blueprint("import_export", __name__, template_folder="../../templates", static_folder="../../static",
               url_prefix=/import_export)
from . import routes  # noqa
