# blueprints/schedule/services.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta, date, datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_
from extensions import db
from models import (
    TimeSlot, Schedule, Homework, Group, Teacher, Subject,
    Room, Building, LessonType,
)

TZ = ZoneInfo("Europe/Berlin")

@dataclass
class DayItem:
    is_break: bool
    date: date
    slot_order: int
    start: str
    end: str
    status: str  # past | now | next | future | break
    is_remote: bool = False
    id: Optional[int] = None          # NEW: id занятия (равен schedule.id)
    lesson_id: Optional[int] = None   # оставим для совместимости
    subject: Optional[str] = None
    teacher: Optional[str] = None
    group: Optional[str] = None
    room: Optional[str] = None
    building: Optional[str] = None
    lesson_type: Optional[str] = None
    homework: Optional[dict] = None   # меняем тип на dict | None

def _inject_homeworks(lesson_dicts):
    ids = [it["id"] for it in lesson_dicts if it.get("id") and not it.get("is_break")]
    if not ids:
        return
    hws = Homework.query.filter(Homework.schedule_id.in_(ids)).all()
    hw_map = {h.schedule_id: h for h in hws}
    for it in lesson_dicts:
        if it.get("is_break"):
            continue
        h = hw_map.get(it["id"])
        if h:
            it["homework"] = {
                "text": h.text,
                "deadline": (h.deadline.isoformat() if h.deadline else None),
            }
        else:
            it["homework"] = None

def _combine_dt(d: date, t) -> datetime:
    # t: datetime.time (naive) -> aware in TZ
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=TZ)

def _status_for(start_dt: datetime, end_dt: datetime, now_dt: datetime) -> str:
    if now_dt < start_dt:  return "future"
    if start_dt <= now_dt < end_dt: return "now"
    return "past"

def _format_time(t) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

def _week_bounds(center: date) -> Tuple[date, date]:
    # ISO week (Mon..Sun)
    start = center - timedelta(days=(center.isoweekday() - 1))
    end = start + timedelta(days=6)
    return start, end

def _load_slots() -> List[TimeSlot]:
    return list(TimeSlot.query.order_by(TimeSlot.order_no).all())

def _base_query(start: date, end: date):
    return (db.session.query(Schedule, Group, Teacher, Subject, Room, Building, LessonType)
            .join(Group, Group.id == Schedule.group_id)
            .join(Teacher, Teacher.id == Schedule.teacher_id)
            .join(Subject, Subject.id == Schedule.subject_id)
            .outerjoin(Room, Room.id == Schedule.room_id)
            .outerjoin(Building, Building.id == Room.building_id)
            .join(LessonType, LessonType.id == Schedule.lesson_type_id)
            .filter(and_(Schedule.date >= start, Schedule.date <= end)))

def _insert_breaks_for_day(day: date, slots: List[TimeSlot], existing: Dict[int, DayItem]) -> List[DayItem]:
    """Возвращает список на день: пары + перерывы ТОЛЬКО между минимум/максимум слотами с занятиями."""
    if not existing:
        return []  # ничего не показываем, если в этот день пар нет
    orders = sorted(existing.keys())
    lo, hi = orders[0], orders[-1]
    result: List[DayItem] = []
    for sl in slots:
        if sl.order_no < lo or sl.order_no > hi:
            continue
        if sl.order_no in existing:
            result.append(existing[sl.order_no])
        else:
            result.append(DayItem(
                is_break=True, date=day, slot_order=sl.order_no,
                start=_format_time(sl.start_time), end=_format_time(sl.end_time),
                status="break",
            ))
    return result

def _mark_next(items: List[DayItem], now_dt: datetime) -> None:
    # отметить первый будущий НЕ break как next
    for it in items:
        if not it.is_break and it.status == "future":
            it.status = "next"
            return

def _build_for_day(day: date, rows: List[Tuple], slots: List[TimeSlot], now_dt: datetime) -> List[DayItem]:
    # rows: список (Schedule,... ) конкретного дня
    by_order: Dict[int, DayItem] = {}
    slot_by_id = {s.id: s for s in slots}
    for sch, grp, tch, subj, room, bld, lt in rows:
        sl = slot_by_id[sch.time_slot_id]
        start_dt = _combine_dt(day, sl.start_time)
        end_dt = _combine_dt(day, sl.end_time)
        item = DayItem(
            is_break=False, date=day, slot_order=sl.order_no,
            start=_format_time(sl.start_time), end=_format_time(sl.end_time),
            status=_status_for(start_dt, end_dt, now_dt),
            is_remote=bool(sch.is_remote),
            id=sch.id,                      # NEW
            lesson_id=sch.id,               # оставляем тоже
            subject=subj.name,
            teacher=tch.full_name,
            group=grp.code,
            room=(room.number if room else None),
            building=(bld.name if bld else None),
            lesson_type=lt.name,
            homework=None,                  # чтобы _inject_homeworks заполнил
        )

    items = _insert_breaks_for_day(day, slots, by_order)
    if day == now_dt.date():
        _mark_next(items, now_dt)
    return items

def schedule_for_group(code: str, at: date, range_: str, now_berlin: Optional[datetime] = None):
    now_dt = now_berlin or datetime.now(TZ)
    slots = _load_slots()
    if range_ == "week":
        start, end = _week_bounds(at)
    else:
        start = end = at

    q = _base_query(start, end).filter(Group.code == code)
    rows = q.order_by(Schedule.date.asc()).all()

    # сгруппировать по дате
    by_day: Dict[date, List[Tuple]] = {}
    for row in rows:
        sch: Schedule = row[0]
        by_day.setdefault(sch.date, []).append(row)

    result = []
    cur = start
    while cur <= end:
        day_items = _build_for_day(cur, by_day.get(cur, []), slots, now_dt)
        if day_items:  # только дни, где есть пары (или перерывы между ними)
            day_dicts = [i.__dict__ for i in day_items]
            _inject_homeworks(day_dicts)
            result.append({"date": cur.isoformat(), "items": [i.__dict__ for i in day_items]})
        cur += timedelta(days=1)
    return {"entity": {"type": "group", "code": code}, "range": range_, "days": result}

def schedule_for_teacher(teacher_id: int, at: date, range_: str, now_berlin: Optional[datetime] = None):
    now_dt = now_berlin or datetime.now(TZ)
    slots = _load_slots()
    if range_ == "week":
        start, end = _week_bounds(at)
    else:
        start = end = at

    q = _base_query(start, end).filter(Teacher.id == teacher_id)
    rows = q.order_by(Schedule.date.asc()).all()

    by_day: Dict[date, List[Tuple]] = {}
    for row in rows:
        sch: Schedule = row[0]
        by_day.setdefault(sch.date, []).append(row)

    result = []
    cur = start
    while cur <= end:
        day_items = _build_for_day(cur, by_day.get(cur, []), slots, now_dt)
        if day_items:
            day_dicts = [i.__dict__ for i in day_items]
            _inject_homeworks(day_dicts)
            result.append({"date": cur.isoformat(), "items": [i.__dict__ for i in day_items]})
        cur += timedelta(days=1)
    return {"entity": {"type": "teacher", "id": teacher_id}, "range": range_, "days": result}

def lesson_details(lesson_id: int) -> Optional[Dict]:
    row = (db.session.query(Schedule, Group, Teacher, Subject, Room, Building, LessonType)
           .join(Group, Group.id == Schedule.group_id)
           .join(Teacher, Teacher.id == Schedule.teacher_id)
           .join(Subject, Subject.id == Schedule.subject_id)
           .outerjoin(Room, Room.id == Schedule.room_id)
           .outerjoin(Building, Building.id == Room.building_id)
           .join(LessonType, LessonType.id == Schedule.lesson_type_id)
           .filter(Schedule.id == lesson_id).first())
    if not row:
        return None
    sch, grp, tch, subj, room, bld, lt = row
    hws = Homework.query.filter_by(schedule_id=sch.id).order_by(Homework.created_at.desc()).all()
    return {
        "id": sch.id,
        "date": sch.date.isoformat(),
        "is_remote": bool(sch.is_remote),
        "group": grp.code,
        "subject": subj.name,
        "teacher": tch.full_name,
        "lesson_type": lt.name,
        "room": (room.number if room else None),
        "building": (bld.name if bld else None),
        "note": sch.note,
        "homework": [{"text": hw.text, "deadline": (hw.deadline.isoformat() if hw.deadline else None),
                      "created_at": hw.created_at.isoformat()} for hw in hws],
    }

def get_teacher_schedule(teacher_id: int, at: date, range_: str, now_berlin: Optional[datetime] = None):
    """
    Адаптер для API: возвращает плоский список lessons + период.
    1) Пытаемся обычной ISO-неделей через schedule_for_teacher().
    2) Если пусто и это запрос без даты (at == today) и range=week,
       пробуем "скользящее окно" [today .. today+7] включительно
       через явный JOIN TimeSlot (без _build_for_day()).
    """
    rng = (range_ or "week").lower()

    # период ISO-недели
    if rng == "week":
        start, end = _week_bounds(at)
    else:
        start = end = at

    data = schedule_for_teacher(teacher_id=teacher_id, at=at, range_=rng, now_berlin=now_berlin)
    lessons: list[dict] = []
    for day in data.get("days", []):
        lessons.extend(day.get("items", []))

    # если уроки уже есть — подмешаем ДЗ и вернём
    if lessons:
        _inject_homeworks(lessons)
        return {"period": {"start": start.isoformat(), "end": end.isoformat()}, "lessons": lessons}

    # --- Fallback: скользящее окно на 7 дней вперёд от today ---
    if rng == "week" and at == date.today():
        start_alt = at
        end_alt = at + timedelta(days=7)  # включительно
        now_dt = now_berlin or datetime.now(TZ)

        rows = (
            db.session.query(
                Schedule, Group, Teacher, Subject, Room, Building, LessonType, TimeSlot
            )
            .join(Group, Group.id == Schedule.group_id)
            .join(Teacher, Teacher.id == Schedule.teacher_id)
            .join(Subject, Subject.id == Schedule.subject_id)
            .outerjoin(Room, Room.id == Schedule.room_id)
            .outerjoin(Building, Building.id == Room.building_id)
            .join(LessonType, LessonType.id == Schedule.lesson_type_id)
            .join(TimeSlot, TimeSlot.id == Schedule.time_slot_id)
            .filter(and_(Schedule.date >= start_alt, Schedule.date <= end_alt))
            .filter(Teacher.id == teacher_id)
            .order_by(Schedule.date.asc(), TimeSlot.order_no.asc())
            .all()
        )

        alt_lessons: list[dict] = []
        first_future_idx = None
        for sch, grp, tch, subj, room, bld, lt, ts in rows:
            start_dt = _combine_dt(sch.date, ts.start_time)
            end_dt = _combine_dt(sch.date, ts.end_time)
            status = _status_for(start_dt, end_dt, now_dt)
            item = {
                "is_break": False,
                "date": sch.date.isoformat(),
                "slot_order": ts.order_no,
                "start": _format_time(ts.start_time),
                "end": _format_time(ts.end_time),
                "status": status,
                "is_remote": bool(sch.is_remote),
                "id": sch.id,
                "lesson_id": sch.id,
                "subject": subj.name,
                "teacher": tch.full_name,
                "group": grp.code,
                "room": (room.number if room else None),
                "building": (bld.name if bld else None),
                "lesson_type": lt.name,
                "homework": None,
            }
            if first_future_idx is None and status == "future" and sch.date == now_dt.date():
                first_future_idx = len(alt_lessons)
            alt_lessons.append(item)

        # пометим первый будущий как "next" (для текущего дня)
        if first_future_idx is not None:
            alt_lessons[first_future_idx]["status"] = "next"

        if alt_lessons:
            _inject_homeworks(alt_lessons)
            return {
                "period": {"start": start_alt.isoformat(), "end": end_alt.isoformat()},
                "lessons": alt_lessons,
            }

    # пусто
    return {"period": {"start": start.isoformat(), "end": end.isoformat()}, "lessons": []}
