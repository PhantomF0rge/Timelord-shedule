from flask import Blueprint, request, jsonify
from .services import run_all_checks
from werkzeug.exceptions import BadRequest

bp = Blueprint("constraints", __name__)
api_bp = Blueprint("constraints_api", __name__)

@api_bp.post("/admin/constraints/check")
def constraints_check():
    try:
        payload = request.get_json()
    except BadRequest:
        return jsonify({"ok": False, "errors": [{"code": "BAD_REQUEST"}]}), 400

    ok, errors = run_all_checks(payload or {})

    if not ok:
        return jsonify({
            "ok": False,
            "errors": [{"code": e.code, "details": e.details} for e in (errors or [])],
        }), 409

    return jsonify({"ok": True, "errors": []}), 200

@api_bp.errorhandler(BadRequest)
def handle_bad_request(err):
    desc = getattr(err, "description", None)
    if isinstance(desc, str) and desc.isupper():
        return jsonify({"ok": False, "errors": [{"code": desc}]}), 409
    if isinstance(desc, (list, tuple)) and all(isinstance(x, str) for x in desc):
        return jsonify({"ok": False, "errors": [{"code": x} for x in desc]}), 409
    if isinstance(desc, dict) and "errors" in desc:
        return jsonify({"ok": False, "errors": desc["errors"]}), 409
    return jsonify({"ok": False, "errors": [{"code": "BAD_REQUEST"}]}), 400
