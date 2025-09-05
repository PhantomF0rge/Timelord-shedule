# blueprints/api/routes.py
from __future__ import annotations
from flask import Blueprint, request, jsonify, abort
from blueprints.search.services import suggest as suggest_service

bp = Blueprint("api", __name__, template_folder="../../templates", static_folder="../../static")

@bp.get("/suggest")
def suggest():
    q = (request.args.get("q") or "").strip()
    typ = (request.args.get("type") or "group").strip().lower()
    try:
        limit = min(50, max(1, int(request.args.get("limit", 10))))
    except ValueError:
        limit = 10

    if not q:
        return jsonify({"items": []})

    if typ not in {"group", "teacher", "subject"}:
        abort(400, description="Invalid type. Use: group|teacher|subject")

    items = suggest_service(q=q, typ=typ, limit=limit)
    return jsonify({"items": items})
