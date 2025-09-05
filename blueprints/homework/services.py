# blueprints/homework/services.py
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import date as dt_date, datetime, timezone
from typing import Optional

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import current_app
from extensions import db
from models import Homework, Schedule, TimeSlot

def _tz():
    try:
        return ZoneInfo("Europe/Berlin")
    except ZoneInfoNotFoundError:
        try:
            import tzdata  # noqa
            return ZoneInfo("Europe/Berlin")
        except Exception:
            return timezone.utc

def _deadline_to_str(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date().isoformat()
    if isinstance(val, dt_date):
        return val.isoformat()
    # запасной вариант
    s = str(val)
    return s.split("T", 1)[0]  # обрежем время, если оно есть

@dataclass
class HomeworkOut:
    id: int
    schedule_id: int
    text: str
    deadline: Optional[str]

def _lesson_end_dt(sch: Schedule, slot: TimeSlot) -> datetime:
    tz = _tz()
    return datetime.combine(sch.date, slot.end_time, tzinfo=tz)

def create_or_update_homework(*, user, lesson_id: int, text: str, deadline: Optional[date]) -> HomeworkOut:
    """Создать/обновить ДЗ для пары. Проверяет владельца и «прошедшую пару»."""
    # 1) найти пару и слот
    sch: Schedule | None = db.session.get(Schedule, lesson_id)
    if not sch:
        raise ValueError("LESSON_NOT_FOUND")

    slot: TimeSlot | None = db.session.get(TimeSlot, sch.time_slot_id)
    if not slot:
        raise ValueError("TIMESLOT_NOT_FOUND")

    # 2) проверки прав
    role = getattr(user, "role", None)
    teacher_id = getattr(user, "teacher_id", None)

    allow_admin_override = bool(current_app.config.get("HOMEWORK_ADMIN_OVERRIDE", True))
    if role != "TEACHER":
        if not (role == "ADMIN" and allow_admin_override):
            raise PermissionError("FORBIDDEN")

    if role == "TEACHER":
        if sch.teacher_id != teacher_id:
            raise PermissionError("NOT_OWNER")

    # 3) прошедшая пара
    allow_past = bool(current_app.config.get("HOMEWORK_ALLOW_PAST", False))
    if not allow_past:
        if _lesson_end_dt(sch, slot) < datetime.now(_tz()):
            raise RuntimeError("PAST_LESSON")

    # 4) upsert
    hw: Homework | None = Homework.query.filter_by(schedule_id=lesson_id).first()
    if hw:
        hw.text = text
        hw.deadline = deadline
    else:
        hw = Homework(schedule_id=lesson_id, text=text, deadline=deadline,
                      created_by_teacher_id=(teacher_id if role == "TEACHER" else None))
        db.session.add(hw)

    db.session.commit()
    return HomeworkOut(
        id=hw.id,
        schedule_id=hw.schedule_id,
        text=hw.text,
        deadline=_deadline_to_str(hw.deadline),
    )
