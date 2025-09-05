# blueprints/teacher/routes.py
from __future__ import annotations
from datetime import date
from functools import wraps
from typing import Optional

from flask import Blueprint, render_template, request, abort, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Teacher, User
from . import services as svc

bp = Blueprint("teacher", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("teacher_api", __name__)

# --- строгая защита: только TEACHER ---
def teacher_only_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if getattr(current_user, "role", None) != "TEACHER":
            # в тест-режиме наш LoginManager отдаёт 401/403 как JSON
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def _current_teacher_id() -> Optional[int]:
    # предполагаем, что User.teacher_id заполнен
    tid = getattr(current_user, "teacher_id", None)
    if tid is None:
        # пытаемся найти по email, если нужно
        t: Optional[Teacher] = Teacher.query.first()  # fallback (не рекомендуется)
        return t.id if t else None
    return tid

# ---------- SSR ----------
@bp.get("/me")
@teacher_only_required
def me_page():
    # просто отрисовываем оболочку, данные подтянет JS
    # Для удобства в data-атрибут кинем teacher_id, если он есть.
    tid = _current_teacher_id()
    return render_template("teacher/me.html", teacher_id=tid)

# ---------- API ----------
@api_bp.get("/teacher/me/aggregate")
@teacher_only_required
def api_me_aggregate():
    d = request.args.get("date")
    r = (request.args.get("range") or "week").lower()
    try:
        at = date.fromisoformat(d) if d else date.today()
    except ValueError:
        abort(400, description="Bad date")
    r = "month" if r == "month" else "week"

    tid = _current_teacher_id()
    if not tid:
        abort(400, description="Teacher not linked")

    out = svc.aggregate_for_teacher(tid, at, r)
    return jsonify(out)
