from __future__ import annotations
from datetime import date, timedelta
from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from . import bp, api_bp
from extensions import db
from models import Schedule, Group, Teacher, Subject, Room, TimeSlot, AuditLog
from blueprints.auth.routes import admin_required

# ---------- PAGES ----------
@bp.get("/admin")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html")

@bp.get("/admin/directory/<entity>")
@login_required
@admin_required
def admin_directory(entity: str):
    # простая страница-обёртка, JS сам стучится в готовые API
    return render_template("admin/directory.html", entity=entity)

@bp.get("/admin/schedule-editor")
@login_required
@admin_required
def schedule_editor():
    return render_template("admin/schedule_editor.html")

# ---------- API (summary для дашборда) ----------
@api_bp.get("/admin/dashboard/summary")
@login_required
@admin_required
def dashboard_summary():
    today = date.today()
    week_to = today + timedelta(days=6)

    groups = db.session.query(Group).count()
    teachers = db.session.query(Teacher).count()
    rooms = db.session.query(Room).count()
    subjects = db.session.query(Subject).count()

    # занятия ближайшей недели
    sched = (db.session.query(Schedule)
             .filter(Schedule.date >= today, Schedule.date <= week_to)
             .all())

    # простая «проверка конфликтов»: совпадение (date, slot) по teacher/group/room
    def _key(*args): return "|".join(map(str, args))
    seen_t, seen_g, seen_r = set(), set(), set()
    conflicts = []
    for s in sched:
        tkey = _key("T", s.date, s.time_slot_id, s.teacher_id)
        gkey = _key("G", s.date, s.time_slot_id, s.group_id)
        rkey = _key("R", s.date, s.time_slot_id, s.room_id)
        for key, code in ((tkey, "TEACHER_BUSY"), (gkey, "GROUP_BUSY"), (rkey, "ROOM_BUSY")):
            if key in (seen_t if code=="TEACHER_BUSY" else seen_g if code=="GROUP_BUSY" else seen_r):
                conflicts.append({"schedule_id": s.id, "code": code})
            else:
                (seen_t if code=="TEACHER_BUSY" else seen_g if code=="GROUP_BUSY" else seen_r).add(key)

    # сведём в короткий ответ
    return jsonify({
        "ok": True,
        "counters": {"groups": groups, "teachers": teachers, "rooms": rooms, "subjects": subjects},
        "week": [{"id": s.id, "date": s.date.isoformat(), "time_slot_id": s.time_slot_id,
                  "group_id": s.group_id, "teacher_id": s.teacher_id, "room_id": s.room_id,
                  "subject_id": s.subject_id} for s in sched],
        "conflicts": conflicts,
    })

# (опционально) быстрый просмотр лога
@api_bp.get("/admin/audit-logs")
@login_required
@admin_required
def audit_logs():
    q = db.session.query(AuditLog).order_by(AuditLog.id.desc()).limit(50).all()
    return jsonify({"ok": True, "items": [
        {"id": a.id, "user_id": a.user_id, "action": a.action, "entity": a.entity,
         "entity_id": a.entity_id, "created_at": a.created_at.isoformat()}
        for a in q
    ]})

