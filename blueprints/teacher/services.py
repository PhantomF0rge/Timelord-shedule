# blueprints/teacher/services.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, time
from typing import Dict, List, Tuple

from sqlalchemy import and_, func
from extensions import db
from models import (
    Schedule, TimeSlot, Teacher, Group, Subject, LessonType, Room, Building
)

@dataclass
class LessonOut:
    id: int
    date: str
    slot_order: int
    start: str
    end: str
    subject: str
    group: str
    lesson_type: str
    is_remote: bool
    room: str | None
    building: str | None
    duration_hours: float

def _week_bounds(center: date) -> Tuple[date, date]:
    start = center - timedelta(days=(center.isoweekday() - 1))  # Mon
    end = start + timedelta(days=6)  # Sun
    return start, end

def _month_bounds(center: date) -> Tuple[date, date]:
    start = center.replace(day=1)
    # next month first day minus one day
    if start.month == 12:
        next_first = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_first = start.replace(month=start.month + 1, day=1)
    end = next_first - timedelta(days=1)
    return start, end

def _fmt(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

def _duration_hours(ts: TimeSlot) -> float:
    # naive times: just compute delta
    start = timedelta(hours=ts.start_time.hour, minutes=ts.start_time.minute)
    end = timedelta(hours=ts.end_time.hour, minutes=ts.end_time.minute)
    return round((end - start).total_seconds() / 3600.0, 2)

def period(at: date, range_: str) -> Tuple[date, date]:
    if range_ == "month":
        return _month_bounds(at)
    # default week
    return _week_bounds(at)

def aggregate_for_teacher(teacher_id: int, at: date, range_: str = "week") -> Dict:
    start, end = period(at, "month" if range_ == "month" else "week")

    # preload slots by id
    slots: List[TimeSlot] = list(TimeSlot.query.order_by(TimeSlot.order_no).all())
    slot_by_id = {s.id: s for s in slots}

    q = (db.session.query(Schedule, Group, Subject, LessonType, Room, Building)
         .join(Group, Group.id == Schedule.group_id)
         .join(Subject, Subject.id == Schedule.subject_id)
         .join(LessonType, LessonType.id == Schedule.lesson_type_id)
         .outerjoin(Room, Room.id == Schedule.room_id)
         .outerjoin(Building, Building.id == Room.building_id)
         .filter(and_(Schedule.teacher_id == teacher_id,
                      Schedule.date >= start, Schedule.date <= end))
         .order_by(Schedule.date.asc()))

    lessons: List[LessonOut] = []
    workdays: set[date] = set()
    total_hours = 0.0

    for sch, grp, subj, lt, room, bld in q.all():
        sl = slot_by_id.get(sch.time_slot_id)
        if not sl:
            # пропускаем «битые» записи
            continue
        workdays.add(sch.date)
        dur = _duration_hours(sl)
        total_hours += dur
        lessons.append(LessonOut(
            id=sch.id,
            date=sch.date.isoformat(),
            slot_order=sl.order_no,
            start=_fmt(sl.start_time),
            end=_fmt(sl.end_time),
            subject=subj.name,
            group=grp.code,
            lesson_type=lt.name,
            is_remote=bool(sch.is_remote),
            room=(room.number if room else None),
            building=(bld.name if bld else None),
            duration_hours=dur,
        ))

    lessons.sort(key=lambda x: (x.date, x.slot_order))
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "range": range_},
        "counts": {
            "work_days": len(workdays),
            "hours": round(total_hours, 2),
            "pairs": len(lessons),
        },
        "lessons": [asdict(l) for l in lessons],
    }
