# blueprints/schedule/routes.py
from __future__ import annotations
from datetime import date, datetime
from flask import Blueprint, render_template, request, abort, jsonify
from blueprints.schedule import services as svc
from flask_login import login_required, current_user
from . import api_bp
from extensions import db
from models import Schedule, TimeSlot, Group, Teacher, Subject, LessonType, Room, AuditLog
from blueprints.auth.routes import admin_required
from blueprints.constraints.services import run_all_checks

bp = Blueprint("schedule", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("schedule_api", __name__)

def _log(action: str, entity_id: int, payload: dict | None = None):
    db.session.add(AuditLog(
        user_id=getattr(current_user, "id", None),
        action=action, entity="schedule", entity_id=entity_id, payload=payload or {}
    ))

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

# ----- ADMIN API -----
@api_bp.get("/admin/schedule")
@login_required
@admin_required
def list_schedule():
    d_from = request.args.get("date_from")
    d_to = request.args.get("date_to")
    q = Schedule.query
    if d_from: q = q.filter(Schedule.date >= date.fromisoformat(d_from))
    if d_to:   q = q.filter(Schedule.date <= date.fromisoformat(d_to))
    items = q.all()
    return jsonify({"ok": True, "items": [
        {"id": s.id, "date": s.date.isoformat(), "time_slot_id": s.time_slot_id,
         "group_id": s.group_id, "teacher_id": s.teacher_id, "room_id": s.room_id,
         "subject_id": s.subject_id, "lesson_type_id": s.lesson_type_id}
        for s in items
    ]})

@api_bp.get("/admin/schedule/lookup")
@login_required
@admin_required
def lookup():
    return jsonify({
        "ok": True,
        "groups": [{"id": x.id, "code": x.code, "name": x.name} for x in Group.query.all()],
        "teachers": [{"id": x.id, "name": x.full_name} for x in Teacher.query.all()],
        "rooms": [{"id": x.id, "number": x.number} for x in Room.query.all()],
        "subjects": [{"id": x.id, "name": x.name} for x in Subject.query.all()],
        "lesson_types": [{"id": x.id, "name": x.name} for x in LessonType.query.all()],
        "timeslots": [{"id": x.id, "order_no": x.order_no} for x in TimeSlot.query.order_by(TimeSlot.order_no).all()],
    })

@api_bp.post("/admin/schedule")
@login_required
@admin_required
def create_schedule():
    js = request.get_json(silent=True) or {}
    payload = {
        "date": js.get("date"),
        "time_slot_id": js.get("time_slot_id"),
        "group_id": js.get("group_id"),
        "subject_id": js.get("subject_id"),
        "lesson_type_id": js.get("lesson_type_id"),
        "teacher_id": js.get("teacher_id"),
        "room_id": js.get("room_id"),
        "is_remote": bool(js.get("is_remote", False)),
        "requires_computers": bool(js.get("requires_computers", False)),
    }
    ok, errors = run_all_checks(payload)
    if not ok:
        return jsonify({"ok": False, "errors": [{"code": e.code} for e in errors]}), 409
    s = Schedule(
        date=date.fromisoformat(payload["date"]),
        time_slot_id=payload["time_slot_id"],
        group_id=payload["group_id"],
        subject_id=payload["subject_id"],
        lesson_type_id=payload["lesson_type_id"],
        teacher_id=payload["teacher_id"],
        room_id=payload["room_id"],
    )
    db.session.add(s); db.session.flush()
    _log("CREATE", s.id, payload)
    db.session.commit()
    return jsonify({"ok": True, "id": s.id}), 201

@api_bp.put("/admin/schedule/<int:sid>")
@login_required
@admin_required
def schedule_update(sid: int):
    s = Schedule.query.get_or_404(sid)
    js = request.get_json(silent=True) or {}

    # Собираем новые значения, подставляя текущие по умолчанию
    new_date = date.fromisoformat(js["date"]) if "date" in js else s.date
    new_time_slot_id = js.get("time_slot_id", s.time_slot_id)
    new_group_id = js.get("group_id", s.group_id)
    new_teacher_id = js.get("teacher_id", s.teacher_id)
    new_room_id = js.get("room_id", s.room_id)
    new_subject_id = js.get("subject_id", s.subject_id)
    new_lesson_type_id = js.get("lesson_type_id", s.lesson_type_id)
    new_is_remote = js.get("is_remote", False if s is None else False)  # у тебя check не требует этого
    new_requires_computers = js.get("requires_computers", False)

    # Если изменений нет — идемпотентный OK
    if (
        new_date == s.date
        and new_time_slot_id == s.time_slot_id
        and new_group_id == s.group_id
        and new_teacher_id == s.teacher_id
        and new_room_id == s.room_id
        and new_subject_id == s.subject_id
        and new_lesson_type_id == s.lesson_type_id
    ):
        return jsonify({"ok": True, "id": s.id}), 200

    # Прогоняем констрейнты на новые значения
    payload = {
        "date": new_date.isoformat(),
        "time_slot_id": new_time_slot_id,
        "group_id": new_group_id,
        "subject_id": new_subject_id,
        "lesson_type_id": new_lesson_type_id,
        "teacher_id": new_teacher_id,
        "room_id": new_room_id,
        "is_remote": new_is_remote,
        "requires_computers": new_requires_computers,
    }

    # Если твой run_all_checks поддерживает исключение текущего расписания — раскомментируй:
    # ok, errors = run_all_checks(payload, exclude_schedule_id=s.id)
    ok, errors = run_all_checks(payload)

    if not ok:
        return jsonify({"ok": False, "errors": [
            {"code": (e.code if hasattr(e, "code") else e.get("code"))} for e in (errors or [])
        ]}), 409

    # Применяем изменения
    s.date = new_date
    s.time_slot_id = new_time_slot_id
    s.group_id = new_group_id
    s.teacher_id = new_teacher_id
    s.room_id = new_room_id
    s.subject_id = new_subject_id
    s.lesson_type_id = new_lesson_type_id

    db.session.commit()
    return jsonify({"ok": True, "id": s.id}), 200

@api_bp.delete("/admin/schedule/<int:sid>")
@login_required
@admin_required
def delete_schedule(sid: int):
    s = Schedule.query.get_or_404(sid)
    db.session.delete(s)
    _log("DELETE", sid, {"id": sid})
    db.session.commit()
    return jsonify({"ok": True})