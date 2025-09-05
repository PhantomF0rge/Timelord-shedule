# blueprints/search/services.py
from __future__ import annotations
from typing import List, Dict
from sqlalchemy import or_, func, case
from extensions import db
from models import Group, Teacher, Subject

def _like(q: str) -> str:
    return f"%{q}%"

def suggest(*, q: str, typ: str, limit: int = 10) -> List[Dict]:
    qn = (q or "").strip()
    if not qn:
        return []

    if typ == "group":
        qy = (
            db.session.query(
                Group.id,
                Group.code.label("label"),
                Group.name.label("hint"),
            )
            .filter(or_(Group.code.ilike(_like(qn)), Group.name.ilike(_like(qn))))
            .order_by(
                case((Group.code.ilike(f"{qn}%"), 0), else_=1),
                func.length(Group.code).asc(),
                Group.code.asc(),
            )
            .limit(limit)
        )
        return [{"type": "group", "id": i, "label": l, "hint": h} for i, l, h in qy.all()]

    if typ == "teacher":
        qy = (
            db.session.query(
                Teacher.id,
                Teacher.full_name.label("label"),
                Teacher.short_name.label("hint"),
            )
            .filter(
                or_(
                    Teacher.full_name.ilike(_like(qn)),
                    Teacher.short_name.ilike(_like(qn)),
                )
            )
            .order_by(
                case((Teacher.full_name.ilike(f"{qn}%"), 0), else_=1),
                func.length(Teacher.full_name).asc(),
                Teacher.full_name.asc(),
            )
            .limit(limit)
        )
        return [{"type": "teacher", "id": i, "label": l, "hint": h} for i, l, h in qy.all()]

    if typ == "subject":
        qy = (
            db.session.query(
                Subject.id,
                Subject.name.label("label"),
                Subject.short_name.label("hint"),
            )
            .filter(or_(Subject.name.ilike(_like(qn)), Subject.short_name.ilike(_like(qn))))
            .order_by(
                case((Subject.name.ilike(f"{qn}%"), 0), else_=1),
                func.length(Subject.name).asc(),
                Subject.name.asc(),
            )
            .limit(limit)
        )
        return [{"type": "subject", "id": i, "label": l, "hint": h} for i, l, h in qy.all()]

    return []
