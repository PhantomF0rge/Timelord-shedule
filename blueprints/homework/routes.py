# blueprints/homework/routes.py
from __future__ import annotations
from datetime import date
from typing import Optional

from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from pydantic import BaseModel, field_validator, ValidationError

from . import services as svc

bp = Blueprint("homework", __name__)
api_bp = Blueprint("homework_api", __name__)

class HomeworkIn(BaseModel):
    lesson_id: int
    text: str
    deadline: Optional[date] = None

    @field_validator("text")
    @classmethod
    def _non_empty(cls, v: str):
        if not v or not v.strip():
            raise ValueError("text_required")
        if len(v) > 5000:
            raise ValueError("too_long")
        return v.strip()

def _json_err(code: str, http: int = 400, detail: str | None = None):
    body = {"error": code}
    if detail:
        body["detail"] = detail
    return jsonify(body), http

@api_bp.post("/homework")
@login_required
def api_homework_upsert():
    payload = request.get_json(silent=True) or {}
    try:
        data = HomeworkIn.model_validate(payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    try:
        out = svc.create_or_update_homework(
            user=current_user,
            lesson_id=data.lesson_id,
            text=data.text,
            deadline=data.deadline
        )
    except PermissionError as pe:
        msg = str(pe)
        if msg == "FORBIDDEN":
            return _json_err("forbidden", 403)
        if msg == "NOT_OWNER":
            return _json_err("not_owner", 403)
        return _json_err("forbidden", 403)
    except ValueError as ve:
        return _json_err(str(ve), 404)
    except RuntimeError as re:
        if str(re) == "PAST_LESSON":
            return _json_err("past_lesson_not_allowed", 400)
        raise

    return jsonify({"ok": True, "homework": out.__dict__})
