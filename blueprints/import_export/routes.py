from flask import jsonify
from . import bp

@bp.get("/ping")
def ping():
    return jsonify(module="import_export", status="ok")
