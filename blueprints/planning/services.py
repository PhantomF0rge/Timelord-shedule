# blueprints/planning/services.py
from __future__ import annotations
import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Dict, Any, Optional, Protocol

from extensions import db
from models import (
    Group, Teacher, Subject, LessonType, TimeSlot, Room, Curriculum, Schedule
)
from blueprints.constraints.services import run_all_checks

# ===== DTO =====
@dataclass
class Proposed:
    date: str
    time_slot_id: int
    group_id: int
    subject_id: int
    lesson_type_id: int
    teacher_id: int
    room_id: int

@dataclass
class Unplaced:
    group_id: int
    subject_id: int
    reason_codes: List[str]
    context: Dict[str, Any]

class PlanningStrategy(Protocol):
    def propose(self, params: Dict[str, Any]) -> Dict[str, Any]:
        ...

def daterange(d_from: date, d_to: date) -> Iterable[date]:
    d = d_from
    while d <= d_to:
        yield d
        d += timedelta(days=1)

def _slot_hours(slot: TimeSlot) -> float:
    return (slot.end_time.hour + slot.end_time.minute / 60) - (slot.start_time.hour + slot.start_time.minute / 60)

# ===== жадная стратегия =====
class GreedyStrategy:
    def propose(self, params: Dict[str, Any]) -> Dict[str, Any]:
        d_from: date = params["date_from"]
        d_to: date = params["date_to"]
        honor_holidays: bool = params.get("honor_holidays", True)

        groups: List[Group] = params["groups"]
        teachers: List[Teacher] = params["teachers"]
        timeslots: List[TimeSlot] = TimeSlot.query.order_by(TimeSlot.order_no.asc()).all()
        rooms: List[Room] = Room.query.all()
        lesson_type: LessonType | None = LessonType.query.first()

        remain_by_group_subject: Dict[tuple[int, int], float] = {}
        for g in groups:
            for cur in Curriculum.query.filter_by(group_id=g.id).all():
                used_hours = 0.0
                for s in Schedule.query.filter_by(group_id=g.id, subject_id=cur.subject_id).all():
                    slot = TimeSlot.query.get(s.time_slot_id)
                    if slot:
                        used_hours += _slot_hours(slot)
                remain_by_group_subject[(g.id, cur.subject_id)] = max((cur.total_hours or 0) - used_hours, 0.0)

        busy_teacher, busy_group, busy_room = set(), set(), set()
        proposed: List[Proposed] = []
        unplaced: List[Unplaced] = []

        for d in daterange(d_from, d_to):
            if honor_holidays and d.weekday() >= 5:
                continue
            for ts in timeslots:
                for g in groups:
                    subjects = sorted(
                        [(sid, rem) for (gid, sid), rem in remain_by_group_subject.items() if gid == g.id and rem > 0],
                        key=lambda x: x[0]
                    )
                    if not subjects:
                        continue
                    placed_for_group_this_slot = False
                    for subject_id, rem_left in subjects:
                        if placed_for_group_this_slot:
                            break
                        reason_codes_acc: set[str] = set()
                        for t in teachers:
                            if (d, ts.id, t.id) in busy_teacher:
                                continue
                            for r in rooms:
                                if (d, ts.id, r.id) in busy_room or (d, ts.id, g.id) in busy_group:
                                    continue
                                requires_computers = bool(getattr(getattr(r, "room_type", None), "requires_computers", False))
                                payload = {
                                    "date": d.isoformat(),
                                    "time_slot_id": ts.id,
                                    "group_id": g.id,
                                    "subject_id": subject_id,
                                    "lesson_type_id": (lesson_type.id if lesson_type else None),
                                    "teacher_id": t.id,
                                    "room_id": r.id,
                                    "is_remote": False,
                                    "requires_computers": requires_computers,
                                }
                                ok, errors = run_all_checks(payload)
                                if ok:
                                    proposed.append(Proposed(
                                        date=d.isoformat(), time_slot_id=ts.id, group_id=g.id,
                                        subject_id=subject_id,
                                        lesson_type_id=(lesson_type.id if lesson_type else 0),
                                        teacher_id=t.id, room_id=r.id
                                    ))
                                    busy_teacher.add((d, ts.id, t.id))
                                    busy_group.add((d, ts.id, g.id))
                                    busy_room.add((d, ts.id, r.id))
                                    remain_by_group_subject[(g.id, subject_id)] = max(rem_left - _slot_hours(ts), 0.0)
                                    placed_for_group_this_slot = True
                                    break
                                else:
                                    for e in errors or []:
                                        code = getattr(e, "code", None) or (e.get("code") if isinstance(e, dict) else None)
                                        if code:
                                            reason_codes_acc.add(code)
                        if not placed_for_group_this_slot and reason_codes_acc:
                            unplaced.append(Unplaced(
                                group_id=g.id, subject_id=subject_id,
                                reason_codes=sorted(reason_codes_acc),
                                context={"date": d.isoformat(), "time_slot_id": ts.id}
                            ))

        return {
            "proposed": [p.__dict__ for p in proposed],
            "unplaced": [u.__dict__ for u in unplaced],
        }

# ===== фасад планировщика =====
@dataclass
class PreviewResult:
    proposed: List[Dict[str, Any]]
    unplaced: List[Dict[str, Any]]

class GreedyPlanner:
    def __init__(self, strategy: Optional[PlanningStrategy] = None):
        self.strategy = strategy or GreedyStrategy()

    def generate(self, *, date_from: date, date_to: date, groups: List[Group], teachers: List[Teacher], honor_holidays: bool) -> PreviewResult:
        res = self.strategy.propose({
            "date_from": date_from,
            "date_to": date_to,
            "groups": groups,
            "teachers": teachers,
            "honor_holidays": honor_holidays,
        })
        return PreviewResult(proposed=res["proposed"], unplaced=res["unplaced"])

# ===== простое in-memory хранилище предпросмотров =====
class PreviewStore:
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}

    def save(self, payload: Dict[str, Any]) -> str:
        pid = secrets.token_urlsafe(8)
        self._data[pid] = payload
        return pid

    def get(self, pid: str) -> Optional[Dict[str, Any]]:
        return self._data.get(pid)

    def delete(self, pid: str) -> None:
        self._data.pop(pid, None)

preview_store = PreviewStore()
