# blueprints/constraints/routes.py
from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest
from .services import run_all_checks

bp = Blueprint("constraints", __name__)
api_bp = Blueprint("constraints_api", __name__)

@api_bp.post("/constraints/check")
def constraints_check():
    payload = request.get_json(silent=True) or {}
    ok, errors = run_all_checks(payload)

    # Нормализуем ошибки в словари
    norm = []
    for e in (errors or []):
        if isinstance(e, dict):
            norm.append(e)
        else:
            norm.append({
                "code": getattr(e, "code", str(e)),
                "details": getattr(e, "details", None),
            })

    if ok:
        return jsonify({"ok": True, "errors": []}), 200
    # ВСЕ бизнес-ошибки — 409
    return jsonify({"ok": False, "errors": norm}), 409

@api_bp.app_errorhandler(BadRequest)
def handle_bad_request(err):
    desc = getattr(err, "description", None)

    # Если description — деловой код(ы), преобразуем в 409
    if isinstance(desc, str) and desc.isupper():
        return jsonify({"ok": False, "errors": [{"code": desc}]}), 409
    if isinstance(desc, (list, tuple)) and all(isinstance(x, str) for x in desc):
        return jsonify({"ok": False, "errors": [{"code": x} for x in desc]}), 409
    if isinstance(desc, dict) and "errors" in desc:
        return jsonify({"ok": False, "errors": desc["errors"]}), 409

    # Иначе это действительно плохой запрос (не бизнес-ошибка)
    return jsonify({"ok": False, "errors": [{"code": "BAD_REQUEST"}]}), 400
