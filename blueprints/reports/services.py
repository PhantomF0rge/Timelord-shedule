# blueprints/reports/services.py
from __future__ import annotations
from datetime import date
from io import StringIO
import csv
from typing import Iterable, Dict, List, Tuple, Optional

from extensions import db
from models import (
    Schedule, TimeSlot, Group, Teacher, Subject, LessonType, Room, Building
)

def _slot_hours(ts: TimeSlot) -> float:
    if not ts:
        return 0.0
    return (ts.end_time.hour + ts.end_time.minute/60) - (ts.start_time.hour + ts.start_time.minute/60)

def _timeslots_map() -> Dict[int, TimeSlot]:
    return {ts.id: ts for ts in TimeSlot.query.all()}

def weekly_schedule_csv(scope: str, scope_id: int, d_from: date, d_to: date) -> str:
    """
    CSV: date;weekday;slot_order;start;end;group_code;group_name;teacher;subject;lesson_type;room;building
    scope ∈ {"group","teacher","building"}
    """
    q = Schedule.query.filter(Schedule.date >= d_from, Schedule.date <= d_to)
    if scope == "group":
        q = q.filter(Schedule.group_id == scope_id)
    elif scope == "teacher":
        q = q.filter(Schedule.teacher_id == scope_id)
    elif scope == "building":
        # отфильтруем по корпусу через подзапрос аудиторий
        room_ids = [r.id for r in Room.query.filter(Room.building_id == scope_id).all()]
        if room_ids:
            q = q.filter(Schedule.room_id.in_(room_ids))
        else:
            q = q.filter(Schedule.room_id == -1)  # пустой
    else:
        q = q.filter(Schedule.id == -1)  # пустой при неверном scope

    rows: List[Tuple] = []
    tmap = _timeslots_map()
    # сортировка стабильная: date, slot
    q = q.order_by(Schedule.date.asc(), Schedule.time_slot_id.asc(), Schedule.id.asc())
    for s in q.all():
        ts = tmap.get(s.time_slot_id)
        g = Group.query.get(s.group_id)
        t = Teacher.query.get(s.teacher_id)
        sub = Subject.query.get(s.subject_id)
        lt = LessonType.query.get(s.lesson_type_id) if s.lesson_type_id else None
        r = Room.query.get(s.room_id) if s.room_id else None
        b = Building.query.get(r.building_id) if r else None
        rows.append((
            s.date.isoformat(),
            s.date.strftime("%A"),
            (ts.order_no if ts else ""),
            (ts.start_time.strftime("%H:%M") if ts else ""),
            (ts.end_time.strftime("%H:%M") if ts else ""),
            getattr(g, "code", ""),
            getattr(g, "name", ""),
            getattr(t, "full_name", ""),
            getattr(sub, "name", ""),
            (getattr(lt, "name", "") if lt else ""),
            getattr(r, "number", ""),
            getattr(b, "name", ""),
        ))

    buf = StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["date","weekday","slot_order","start","end","group_code","group_name","teacher","subject","lesson_type","room","building"])
    w.writerows(rows)
    return buf.getvalue()

def teacher_hours_csv(d_from: date, d_to: date, teacher_ids: Optional[List[int]] = None) -> str:
    """
    CSV: teacher_id;teacher;total_hours
    """
    tmap = _timeslots_map()
    q = Schedule.query.filter(Schedule.date >= d_from, Schedule.date <= d_to)
    if teacher_ids:
        q = q.filter(Schedule.teacher_id.in_(teacher_ids))

    totals: Dict[int, float] = {}
    names: Dict[int, str] = {}
    for s in q.all():
        ts = tmap.get(s.time_slot_id)
        hrs = _slot_hours(ts)
        totals[s.teacher_id] = totals.get(s.teacher_id, 0.0) + hrs
    if totals:
        for tid in totals.keys():
            t = Teacher.query.get(tid)
            names[tid] = getattr(t, "full_name", str(tid))

    buf = StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["teacher_id", "teacher", "total_hours"])
    for tid in sorted(totals.keys()):
        w.writerow([tid, names.get(tid, str(tid)), f"{totals[tid]:.2f}"])
    return buf.getvalue()

def room_utilization_csv(d_from: date, d_to: date, building_id: Optional[int] = None) -> str:
    """
    CSV: building;room;slots_used;slots_total;hours_used;utilization_pct
    utilization_pct = slots_used / slots_total * 100
    """
    # список рабочих дат в диапазоне (без выходов на праздники — по ТЗ не требуется, считаем все дни)
    days_count = (d_to - d_from).days + 1
    timeslots = TimeSlot.query.order_by(TimeSlot.order_no.asc()).all()
    slots_per_day = len(timeslots)
    slot_hours = {ts.id: _slot_hours(ts) for ts in timeslots}

    rooms_q = Room.query
    if building_id:
        rooms_q = rooms_q.filter(Room.building_id == building_id)
    rooms = rooms_q.all()
    bmap = {b.id: b for b in Building.query.all()}

    # посчитаем использованные слоты и часы
    q = Schedule.query.filter(Schedule.date >= d_from, Schedule.date <= d_to)
    if building_id:
        q = q.join(Room, Room.id == Schedule.room_id).filter(Room.building_id == building_id)

    used_slots_by_room: Dict[int, int] = {}
    used_hours_by_room: Dict[int, float] = {}
    for s in q.all():
        used_slots_by_room[s.room_id] = used_slots_by_room.get(s.room_id, 0) + 1
        used_hours_by_room[s.room_id] = used_hours_by_room.get(s.room_id, 0.0) + slot_hours.get(s.time_slot_id, 0.0)

    buf = StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["building","room","slots_used","slots_total","hours_used","utilization_pct"])
    total_slots = slots_per_day * days_count if slots_per_day else 0
    for r in sorted(rooms, key=lambda x: (x.building_id, x.number)):
        b = bmap.get(r.building_id)
        used = used_slots_by_room.get(r.id, 0)
        hrs = used_hours_by_room.get(r.id, 0.0)
        util = (used / total_slots * 100.0) if total_slots else 0.0
        w.writerow([
            getattr(b, "name", ""),
            r.number,
            used,
            total_slots,
            f"{hrs:.2f}",
            f"{util:.2f}",
        ])
    return buf.getvalue()
