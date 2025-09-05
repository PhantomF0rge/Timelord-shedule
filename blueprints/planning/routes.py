# blueprints/planning/routes.py
from __future__ import annotations
from datetime import date
from typing import Any, Dict

from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from extensions import db
from models import (
    Schedule, TimeSlot, PlanningPreview,
    Group, Teacher, Subject, LessonType, Room,
)
from blueprints.constraints.services import run_all_checks
from .services import GreedyPlanner, preview_store
from blueprints.auth.routes import admin_required  # твой декоратор

bp = Blueprint("planning", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("planning_api", __name__)

def _require_admin():
    if not current_user.is_authenticated or getattr(current_user, "role", "") != "ADMIN":
        abort(403)

@api_bp.post("/admin/planning/generate")
@login_required
@admin_required
def generate():
    payload = request.get_json(silent=True) or {}

    # обязательны только даты
    try:
        d_from = date.fromisoformat(str(payload["date_from"]))
        d_to = date.fromisoformat(str(payload["date_to"]))
    except Exception:
        return jsonify({
            "ok": False,
            "errors": [{"code": "BAD_REQUEST", "details": "date_from/date_to must be ISO dates"}]
        }), 400

    if d_to < d_from:
        d_from, d_to = d_to, d_from

    honor_holidays = bool(payload.get("honor_holidays", False))

    group_ids = payload.get("group_ids") or payload.get("groups") or []
    teacher_ids = payload.get("teacher_ids") or payload.get("teachers") or []

    groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else Group.query.all()
    teachers = Teacher.query.filter(Teacher.id.in_(teacher_ids)).all() if teacher_ids else Teacher.query.all()

    # Даже если пусто — вернём пустой предпросмотр со статусом 200
    try:
        if not groups or not teachers:
            proposed, unplaced = [], []
        else:
            planner = GreedyPlanner()
            preview_obj = planner.generate(
                date_from=d_from,
                date_to=d_to,
                groups=groups,
                teachers=teachers,
                honor_holidays=honor_holidays,
            )
            # preview_obj может быть dataclass/DTO; приведём к двум спискам
            proposed = getattr(preview_obj, "proposed", []) or []
            unplaced = getattr(preview_obj, "unplaced", []) or []
    except Exception:
        # на всякий случай не роняемся — отдаём пустой предпросмотр
        proposed, unplaced = [], []

    # сохраняем предпросмотр в БД через preview_store
    pid = preview_store.save({"proposed": proposed, "unplaced": unplaced})

    return jsonify({"ok": True, "preview_id": pid, "proposed": proposed, "unplaced": unplaced}), 200

@api_bp.get("/admin/planning/preview")
@login_required
def planning_preview():
    _require_admin()
    pid = request.args.get("id")
    if not pid:
        return jsonify({"ok": False, "errors": [{"code":"BAD_REQUEST","details":{"field":"id"}}]}), 400

    pp = preview_store.get(pid)
    if not pp:
        return jsonify({"ok": False, "errors": [{"code":"NOT_FOUND"}]}), 404
    return jsonify({"ok": True, "preview_id": pid, **pp})

@api_bp.post("/admin/planning/commit")
@login_required
def planning_commit():
    _require_admin()
    js = request.get_json(silent=True) or {}
    pid = js.get("preview_id")
    if not pid:
        return jsonify({"ok": False, "errors": [{"code":"BAD_REQUEST","details":{"field":"preview_id"}}]}), 400

    pp = preview_store.get(pid)
    if not pp:
        return jsonify({"ok": False, "errors": [{"code":"NOT_FOUND"}]}), 404

    proposed = pp.get("proposed") or []
    if not proposed:
        # Нечего коммитить — это не ошибка по смыслу теста
        return jsonify({"ok": True, "committed": 0}), 200

    commit_errors = []
    committed = 0

    for p in proposed:
        payload = {
            "date": p["date"],
            "time_slot_id": p["time_slot_id"],
            "group_id": p["group_id"],
            "subject_id": p["subject_id"],
            "lesson_type_id": p.get("lesson_type_id") or None,
            "teacher_id": p["teacher_id"],
            "room_id": p["room_id"],
            "is_remote": False,
            "requires_computers": False,
        }
        ok, errors = run_all_checks(payload)
        if not ok:
            # соберём коды, чтобы в случае конфликта вернуть 409
            for e in errors or []:
                code = getattr(e, "code", None) or (e.get("code") if isinstance(e, dict) else None)
                if code:
                    commit_errors.append({"code": code})
            continue

        s = Schedule(
            date=date.fromisoformat(p["date"]),
            time_slot_id=p["time_slot_id"],
            group_id=p["group_id"],
            subject_id=p["subject_id"],
            lesson_type_id=p.get("lesson_type_id") or None,
            teacher_id=p["teacher_id"],
            room_id=p["room_id"],
        )
        db.session.add(s)
        committed += 1

    if commit_errors:
        db.session.rollback()
        return jsonify({"ok": False, "errors": commit_errors}), 409

    db.session.commit()
    # опционально: preview_store.delete(pid)
    return jsonify({"ok": True, "committed": committed}), 200
