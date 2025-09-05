from flask import jsonify, request
from . import bp

@bp.get("/health")
def api_health():
    return jsonify(api="v1", status="ok")
