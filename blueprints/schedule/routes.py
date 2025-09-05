# blueprints/schedule/routes.py
from __future__ import annotations
from datetime import date, datetime
from flask import Blueprint, render_template, request, abort, jsonify
from blueprints.schedule import services as svc

bp = Blueprint("schedule", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("schedule_api", __name__)

# ---------- SSR страницы ----------
@bp.get("/")
def index():
    # простая страница-переходник
    return render_template("schedule/index.html")

@bp.get("/group/<code>")
def group_page(code: str):
    d = request.args.get("date")
    r = (request.args.get("range") or "day").lower()
    try:
        at = date.fromisoformat(d) if d else date.today()
    except ValueError:
        abort(400, description="Bad date")
    r = "week" if r == "week" else "day"
    data = svc.schedule_for_group(code, at, r)
    return render_template("schedule/table.html", mode="group", payload=data)

@bp.get("/teacher/<int:tid>")
def teacher_page(tid: int):
    d = request.args.get("date")
    r = (request.args.get("range") or "day").lower()
    try:
        at = date.fromisoformat(d) if d else date.today()
    except ValueError:
        abort(400, description="Bad date")
    r = "week" if r == "week" else "day"
    data = svc.schedule_for_teacher(tid, at, r)
    return render_template("schedule/table.html", mode="teacher", payload=data)

# ---------- API ----------
@api_bp.get("/schedule/group/<code>")
def api_schedule_group(code: str):
    d = request.args.get("date")
    r = (request.args.get("range") or "day").lower()
    try:
        at = date.fromisoformat(d) if d else date.today()
    except ValueError:
        abort(400, description="Bad date")
    r = "week" if r == "week" else "day"
    return jsonify(svc.schedule_for_group(code, at, r))

@api_bp.get("/schedule/teacher/<int:teacher_id>")
def api_schedule_teacher(teacher_id: int):
    d = request.args.get("date")
    rng = (request.args.get("range") or "week").lower()
    try:
        at = date.fromisoformat(d) if d else date.today()
    except ValueError:
        abort(400, description="Bad date")

    data = svc.get_teacher_schedule(teacher_id=teacher_id, at=at, range_=rng)
    out = {"period": data.get("period"), "lessons": data.get("lessons", [])}

    if not out["lessons"]:
        return jsonify({"error": "not_found"}), 404  # важно для фоллбэка в тесте

    return jsonify(out)

@api_bp.get("/lesson/<int:lid>")
def api_lesson(lid: int):
    data = svc.lesson_details(lid)
    if not data:
        abort(404)
    return jsonify(data)
