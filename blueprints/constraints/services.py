# blueprints/constraints/services.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from models import (
    db, Group, Room, Building, RoomType, TimeSlot, Schedule,
    WorkloadLimit, TeacherAvailability, Curriculum
)


@dataclass
class CheckError:
    code: str
    details: dict


def _slot_hours(slot: TimeSlot) -> float:
    """Продолжительность слота в часах."""
    # берём любую "фиктивную" дату — важны только time()
    dt0 = datetime.combine(date(2000, 1, 1), slot.start_time)
    dt1 = datetime.combine(date(2000, 1, 1), slot.end_time)
    return max(0, (dt1 - dt0).seconds) / 3600.0


def _week_bounds(d: date) -> tuple[date, date]:
    """Понедельник..воскресенье (end не включительно)"""
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=7)
    return start, end


def check_room_capacity(group: Group, room: Room) -> list[CheckError]:
    if group and room and group.students_count and room.capacity is not None:
        if group.students_count > room.capacity:
            return [CheckError(
                code="ROOM_CAPACITY_EXCEEDED",
                details={"group_id": group.id, "room_id": room.id,
                         "students": group.students_count, "capacity": room.capacity}
            )]
    return []


def check_room_computers(group: Group, room: Room, requires_computers: bool) -> list[CheckError]:
    if not requires_computers or not room:
        return []
    cnt = room.computers_count or 0
    if group.students_count > cnt:
        return [CheckError(
            code="ROOM_COMPUTERS_NOT_ENOUGH",
            details={"group_id": group.id, "room_id": room.id,
                     "students": group.students_count, "computers": cnt}
        )]
    return []


def check_invalid_building(group: Group, room: Room) -> list[CheckError]:
    if not group or not room:
        return []
    b: Building | None = Building.query.get(room.building_id)
    if b and b.type and group.education_level and b.type != group.education_level:
        return [CheckError(
            code="INVALID_BUILDING",
            details={"group_id": group.id, "room_id": room.id,
                     "building_type": b.type, "education_level": group.education_level}
        )]
    return []


def check_busy(d: date, time_slot_id: int,
               teacher_id: int | None, group_id: int | None, room_id: int | None) -> list[CheckError]:
    """Конфликты занятости в конкретный день и слот."""
    errors: list[CheckError] = []
    existing: list[Schedule] = Schedule.query.filter_by(date=d, time_slot_id=time_slot_id).all()
    for s in existing:
        if teacher_id and s.teacher_id == teacher_id and \
                not any(e.code == "TEACHER_BUSY" for e in errors):
            errors.append(CheckError(code="TEACHER_BUSY", details={"schedule_id": s.id}))
        if group_id and s.group_id == group_id and \
                not any(e.code == "GROUP_BUSY" for e in errors):
            errors.append(CheckError(code="GROUP_BUSY", details={"schedule_id": s.id}))
        if room_id and s.room_id == room_id and \
                not any(e.code == "ROOM_BUSY" for e in errors):
            errors.append(CheckError(code="ROOM_BUSY", details={"schedule_id": s.id}))
    return errors


def check_teacher_limit(d: date, time_slot_id: int, teacher_id: int | None) -> list[CheckError]:
    if not teacher_id:
        return []
    wl: WorkloadLimit | None = WorkloadLimit.query.filter_by(teacher_id=teacher_id).first()
    if not wl or wl.hours_per_week is None:
        return []
    slot = TimeSlot.query.get(time_slot_id)
    if not slot:
        return []
    start, end = _week_bounds(d)
    week_sched: list[Schedule] = (
        Schedule.query
        .filter(Schedule.teacher_id == teacher_id,
                Schedule.date >= start, Schedule.date < end)
        .all()
    )
    total_hours = sum(_slot_hours(TimeSlot.query.get(s.time_slot_id)) for s in week_sched) + _slot_hours(slot)
    if total_hours > wl.hours_per_week:
        return [CheckError(
            code="TEACHER_LIMIT_EXCEEDED",
            details={"teacher_id": teacher_id, "hours": total_hours, "limit": wl.hours_per_week}
        )]
    return []


def check_teacher_availability(d: date, time_slot_id: int, teacher_id: int | None) -> list[CheckError]:
    if not teacher_id:
        return []
    slot = TimeSlot.query.get(time_slot_id)
    if not slot:
        return []
    weekday = d.weekday()
    av: TeacherAvailability | None = TeacherAvailability.query.filter_by(
        teacher_id=teacher_id, weekday=weekday
    ).first()

    # Правило: нет записи — считаем недоступен; is_day_off=True — недоступен;
    # если есть окна — слот должен полностью влезать внутрь.
    if av is None or av.is_day_off:
        return [CheckError(code="TEACHER_NOT_AVAILABLE",
                           details={"teacher_id": teacher_id, "weekday": weekday})]
    if (av.available_from and slot.start_time < av.available_from) \
            or (av.available_to and slot.end_time > av.available_to):
        return [CheckError(code="TEACHER_NOT_AVAILABLE",
                           details={"teacher_id": teacher_id, "weekday": weekday,
                                    "from": av.available_from.isoformat() if av.available_from else None,
                                    "to": av.available_to.isoformat() if av.available_to else None})]
    return []


def check_curriculum(group_id: int | None, subject_id: int | None, time_slot_id: int | None) -> list[CheckError]:
    if not group_id or not subject_id or not time_slot_id:
        return []
    cur: Curriculum | None = Curriculum.query.filter_by(group_id=group_id, subject_id=subject_id).first()
    if not cur or cur.total_hours is None:
        return []
    # суммируем уже назначенные часы по этой группе и предмету за всё время
    sched: list[Schedule] = Schedule.query.filter_by(group_id=group_id, subject_id=subject_id).all()
    used = sum(_slot_hours(TimeSlot.query.get(s.time_slot_id)) for s in sched)
    slot = TimeSlot.query.get(time_slot_id)
    planned = used + ( _slot_hours(slot) if slot else 0.0 )
    if planned > cur.total_hours:
        return [CheckError(
            code="CURRICULUM_HOURS_EXCEEDED",
            details={"group_id": group_id, "subject_id": subject_id,
                     "used_hours": used, "planned_hours": planned, "limit": cur.total_hours}
        )]
    return []


def run_all_checks(payload: dict) -> tuple[bool, list[CheckError]]:
    # обязательный минимум для всех проверок
    required = ["date", "group_id", "subject_id", "teacher_id", "time_slot_id"]
    missing = [k for k in required if k not in payload]
    if missing:
        return False, [CheckError(code="BAD_REQUEST", details={"missing": missing})]

    try:
        d = date.fromisoformat(str(payload["date"]))
        group_id = int(payload["group_id"])
        subject_id = int(payload["subject_id"])
        teacher_id = int(payload["teacher_id"])
        time_slot_id = int(payload["time_slot_id"])
    except Exception as e:
        return False, [CheckError(code="BAD_REQUEST", details={"reason": f"parse_error: {e}"})]

    # lesson_type_id в проверках не используется — делаем опциональным
    lesson_type_id = payload.get("lesson_type_id")  # noqa: F841

    room_id = payload.get("room_id")
    room_id = int(room_id) if room_id is not None else None
    requires_computers = bool(payload.get("requires_computers", False))
    is_remote = bool(payload.get("is_remote", False))

    group = Group.query.get(group_id)
    room = Room.query.get(room_id) if room_id else None

    errors: list[CheckError] = []

    # 1) Проверки занятости (аудитория — только если она указана)
    errors += check_busy(d, time_slot_id, teacher_id, group_id, room_id if not is_remote else None)

    # 2) Лимит часов преподавателя
    errors += check_teacher_limit(d, time_slot_id, teacher_id)

    # 3) Доступность преподавателя по графику/выходным
    errors += check_teacher_availability(d, time_slot_id, teacher_id)

    # 4) Учебный план (остаток часов)
    errors += check_curriculum(group_id, subject_id, time_slot_id)

    # 5) Если занятие очное — аудитория: вместимость, ПК, корпус
    if not is_remote and room:
        errors += check_room_capacity(group, room)
        errors += check_room_computers(group, room, requires_computers)
        errors += check_invalid_building(group, room)

    ok = len(errors) == 0
    return ok, errors
