from flask import jsonify, request
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import date as _date, datetime as _dt, timedelta as _td

from . import bp
from extensions import db


# ---------- утилиты ----------
def _to_hhmm(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v[:5]
    try:
        return v.strftime("%H:%M")
    except Exception:
        return str(v)[:5]


def _to_minutes(v):
    # принимает datetime.time или строку "HH:MM"
    if v is None:
        return None
    try:
        if isinstance(v, str):
            h, m = v[:5].split(":")
            return int(h) * 60 + int(m)
        return v.hour * 60 + v.minute
    except Exception:
        return None


def _try_import(module_path, class_name):
    try:
        mod = __import__(module_path, fromlist=[class_name])
        return getattr(mod, class_name, None)
    except Exception:
        return None


def _models():
    """
    Ленивая загрузка моделей. Возвращает dict с тем, что удалось импортировать.
    Ничего не выбрасывает — обработчики сами решают, что делать, если чего-то нет.
    """
    return {
        "Group": _try_import("models.group", "Group")
                 or _try_import("models.groups", "Group"),

        "TimeSlot": _try_import("models.timeslot", "TimeSlot")
                    or _try_import("models.time_slot", "TimeSlot")
                    or _try_import("models.time_slots", "TimeSlot")
                    or _try_import("models.slot", "TimeSlot"),

        "Lesson": _try_import("models.lesson", "Lesson")
                  or _try_import("models.lessons", "Lesson"),

        "Subject": _try_import("models.subject", "Subject")
                   or _try_import("models.subjects", "Subject"),

        "Teacher": _try_import("models.teacher", "Teacher")
                   or _try_import("models.teachers", "Teacher"),

        "Room": _try_import("models.room", "Room")
                or _try_import("models.rooms", "Room"),

        "LessonType": _try_import("models.lesson_type", "LessonType")
                      or _try_import("models.lesson_types", "LessonType")
                      or _try_import("models.type", "LessonType"),

        "Homework": _try_import("models.homework", "Homework")
                    or _try_import("models.homeworks", "Homework"),
    }


# ---------- /api/v1/suggest ----------
@bp.get("/suggest")
def suggest():
    """
    GET /api/v1/suggest?q=&limit=
    Возвращает подсказки из групп/преподавателей/дисциплин.
    Формат items: {id, type, label, code?}
    """
    M = _models()
    Group = M["Group"]
    Teacher = M["Teacher"]
    Subject = M["Subject"]

    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 10)
    items = []

    if not q:
        return jsonify({"items": []})

    # Если какой-то модели нет — просто пропускаем соответствующий раздел.
    if Group is not None:
        groups = (
            db.session.query(Group)
            .filter(
                (func.lower(Group.code).like(f"%{q.lower()}%")) |
                (func.lower(Group.name).like(f"%{q.lower()}%"))
            )
            .order_by(Group.code.asc())
            .limit(limit)
            .all()
        )
        for g in groups:
            items.append({
                "id": g.id,
                "type": "group",
                "label": f"{getattr(g, 'code', '')} — {getattr(g, 'name', '')}".strip(" —"),
                "code": getattr(g, "code", None)
            })

    if Teacher is not None:
        teachers = (
            db.session.query(Teacher)
            .filter(func.lower(Teacher.full_name).like(f"%{q.lower()}%"))
            .order_by(Teacher.full_name.asc())
            .limit(limit)
            .all()
        )
        for t in teachers:
            items.append({
                "id": t.id,
                "type": "teacher",
                "label": getattr(t, "full_name", "Преподаватель")
            })

    if Subject is not None:
        subjs = (
            db.session.query(Subject)
            .filter(func.lower(Subject.name).like(f"%{q.lower()}%"))
            .order_by(Subject.name.asc())
            .limit(limit)
            .all()
        )
        for s in subjs:
            items.append({
                "id": s.id,
                "type": "subject",
                "label": getattr(s, "name", "Дисциплина")
            })

    return jsonify({"items": items})


# ---------- /api/v1/schedule/group/<code> ----------
@bp.get("/schedule/group/<code>")
def schedule_group(code: str):
    """
    GET /api/v1/schedule/group/<code>?date=YYYY-MM-DD&range=day|week
    - range=day  -> {"group_code", "date", "lessons":[...]}
    - range=week -> {"group_code","range":"week","from","to","days":[{"date","lessons":[...]}]}
    На каждом дне автоматически вставляем «перерывы» по полной сетке TimeSlot.
    """
    from .services.schedule_utils import insert_breaks

    M = _models()
    Group = M["Group"]
    TimeSlot = M["TimeSlot"]
    Lesson = M["Lesson"]
    Subject = M["Subject"]
    Teacher = M["Teacher"]
    Room = M["Room"]
    LessonType = M["LessonType"]
    Homework = M["Homework"]
    HAS_HOMEWORK = Homework is not None

    def _parse_date(s):
        try:
            return _dt.strptime((s or "").strip(), "%Y-%m-%d").date()
        except Exception:
            return _date.today()

    rng = (request.args.get("range") or "day").lower()
    anchor_date = _parse_date(request.args.get("date"))

    # критичные модели
    if not all([Group, TimeSlot, Lesson]):
        if rng == "week":
            # неделя: пустые дни
            dow = anchor_date.weekday()
            monday = anchor_date - _td(days=dow)
            days = [(monday + _td(days=i)).isoformat() for i in range(7)]
            return jsonify({
                "group_code": code, "range": "week",
                "from": days[0], "to": days[-1],
                "days": [{"date": d, "lessons": []} for d in days]
            })
        return jsonify({"group_code": code, "date": anchor_date.isoformat(), "lessons": []})

    # найти группу
    group = (
        db.session.query(Group).filter(func.lower(Group.code) == code.lower()).first()
    ) or (
        db.session.query(Group).filter(func.lower(Group.code).like(f"%{code.lower()}%")).first()
    )
    if not group:
        if rng == "week":
            dow = anchor_date.weekday()
            monday = anchor_date - _td(days=dow)
            days = [(monday + _td(days=i)).isoformat() for i in range(7)]
            return jsonify({
                "group_code": code, "range": "week",
                "from": days[0], "to": days[-1],
                "days": [{"date": d, "lessons": []} for d in days]
            })
        return jsonify({"group_code": code, "date": anchor_date.isoformat(), "lessons": []})

    # сетка слотов
    order_col = getattr(TimeSlot, "order_no", None) or getattr(TimeSlot, "order", None) or getattr(TimeSlot, "id")
    slots = db.session.query(TimeSlot).order_by(order_col.asc()).all()

    # ---------- режим DAY ----------
    if rng == "day":
        rows = (
            db.session.query(Lesson)
            .options(
                joinedload(Lesson.subject),
                joinedload(Lesson.teacher),
                joinedload(Lesson.room),
                joinedload(Lesson.lesson_type),
                joinedload(Lesson.time_slot),
            )
            .filter(
                getattr(Lesson, "group_id") == getattr(group, "id"),
                getattr(Lesson, "date") == anchor_date
            )
            .order_by(getattr(Lesson, "order_no").asc())
            .all()
        )

        def _lesson_json(l):
            ts_rel = getattr(l, "time_slot", None)
            if ts_rel:
                order_no = getattr(ts_rel, "order_no", getattr(ts_rel, "order", None))
                start_hm = _to_hhmm(getattr(ts_rel, "start_time", getattr(ts_rel, "start", None)))
                end_hm = _to_hhmm(getattr(ts_rel, "end_time", getattr(ts_rel, "end", None)))
            else:
                order_no = getattr(l, "order_no", None)
                start_hm = _to_hhmm(getattr(l, "start_time", None))
                end_hm = _to_hhmm(getattr(l, "end_time", None))

            subj = getattr(l, "subject", None)
            subj_name = getattr(subj, "name", "Дисциплина") if subj else "Дисциплина"

            tch = getattr(l, "teacher", None)
            teacher_full = "Преподаватель"
            if tch:
                teacher_full = getattr(tch, "full_name", None) or " ".join(
                    [getattr(tch, "last_name", ""), getattr(tch, "first_name", ""), getattr(tch, "middle_name", "")]
                ).strip() or "Преподаватель"

            room = getattr(l, "room", None)
            room_number = getattr(room, "number", None) if room else None

            lt = getattr(l, "lesson_type", None)
            type_name = getattr(lt, "name", "Занятие") if lt else "Занятие"

            hw_text = None
            if HAS_HOMEWORK:
                hw_rel = getattr(l, "homework", None)
                if hw_rel and getattr(hw_rel, "text", None):
                    hw_text = hw_rel.text
                else:
                    hws = getattr(l, "homeworks", None)
                    if hws and len(hws) > 0 and getattr(hws[0], "text", None):
                        hw_text = hws[0].text

            return {
                "is_break": False,
                "subject": {"name": subj_name},
                "teacher": {"full_name": teacher_full},
                "time_slot": {
                    "order_no": order_no,
                    "start_time": start_hm,
                    "end_time": end_hm,
                },
                "room": {"number": room_number} if room_number else None,
                "lesson_type": {"name": type_name},
                "is_remote": bool(getattr(l, "is_remote", False)),
                "homework": {"text": hw_text} if hw_text else None,
            }

        payload = [ _lesson_json(l) for l in rows ]
        payload = insert_breaks(slots, payload)

        return jsonify({
            "group_code": getattr(group, "code", code),
            "date": anchor_date.isoformat(),
            "lessons": payload
        })

    # ---------- режим WEEK ----------
    dow = anchor_date.weekday()  # 0=Mon
    monday = anchor_date - _td(days=dow)
    sunday = monday + _td(days=6)

    rows = (
        db.session.query(Lesson)
        .options(
            joinedload(Lesson.subject),
            joinedload(Lesson.teacher),
            joinedload(Lesson.room),
            joinedload(Lesson.lesson_type),
            joinedload(Lesson.time_slot),
        )
        .filter(
            getattr(Lesson, "group_id") == getattr(group, "id"),
            getattr(Lesson, "date") >= monday,
            getattr(Lesson, "date") <= sunday,
        )
        .order_by(getattr(Lesson, "date").asc(), getattr(Lesson, "order_no").asc())
        .all()
    )

    # сгруппируем по дате
    by_date = { (monday + _td(days=i)): [] for i in range(7) }

    def _lesson_json(l):
        ts_rel = getattr(l, "time_slot", None)
        if ts_rel:
            order_no = getattr(ts_rel, "order_no", getattr(ts_rel, "order", None))
            start_hm = _to_hhmm(getattr(ts_rel, "start_time", getattr(ts_rel, "start", None)))
            end_hm = _to_hhmm(getattr(ts_rel, "end_time", getattr(ts_rel, "end", None)))
        else:
            order_no = getattr(l, "order_no", None)
            start_hm = _to_hhmm(getattr(l, "start_time", None))
            end_hm = _to_hhmm(getattr(l, "end_time", None))

        subj = getattr(l, "subject", None)
        subj_name = getattr(subj, "name", "Дисциплина") if subj else "Дисциплина"

        tch = getattr(l, "teacher", None)
        teacher_full = "Преподаватель"
        if tch:
            teacher_full = getattr(tch, "full_name", None) or " ".join(
                [getattr(tch, "last_name", ""), getattr(tch, "first_name", ""), getattr(tch, "middle_name", "")]
            ).strip() or "Преподаватель"

        room = getattr(l, "room", None)
        room_number = getattr(room, "number", None) if room else None

        lt = getattr(l, "lesson_type", None)
        type_name = getattr(lt, "name", "Занятие") if lt else "Занятие"

        hw_text = None
        if HAS_HOMEWORK:
            hw_rel = getattr(l, "homework", None)
            if hw_rel and getattr(hw_rel, "text", None):
                hw_text = hw_rel.text
            else:
                hws = getattr(l, "homeworks", None)
                if hws and len(hws) > 0 and getattr(hws[0], "text", None):
                    hw_text = hws[0].text

        return {
            "is_break": False,
            "subject": {"name": subj_name},
            "teacher": {"full_name": teacher_full},
            "time_slot": {
                "order_no": order_no,
                "start_time": start_hm,
                "end_time": end_hm,
            },
            "room": {"number": room_number} if room_number else None,
            "lesson_type": {"name": type_name},
            "is_remote": bool(getattr(l, "is_remote", False)),
            "homework": {"text": hw_text} if hw_text else None,
        }

    for l in rows:
        d = getattr(l, "date")
        by_date[d].append(_lesson_json(l))

    days_payload = []
    for i in range(7):
        d = (monday + _td(days=i))
        payload = insert_breaks(slots, list(by_date.get(d, [])))
        days_payload.append({"date": d.isoformat(), "lessons": payload})

    return jsonify({
        "group_code": getattr(group, "code", code),
        "range": "week",
        "from": monday.isoformat(),
        "to": sunday.isoformat(),
        "days": days_payload
    })

# ---------- /api/v1/schedule/teacher/<teacher_ref> ----------
@bp.get("/schedule/teacher/<teacher_ref>")
def schedule_teacher(teacher_ref: str):
    """
    GET /api/v1/schedule/teacher/<teacher_ref>?from=YYYY-MM-DD&to=YYYY-MM-DD
    teacher_ref: числовой id ИЛИ строка (поиск по full_name, case-insensitive, частичное совпадение).
    Ответ: список занятий + агрегаты (total_days, total_lessons, total_hours).
    """
    M = _models()
    TimeSlot = M["TimeSlot"]
    Lesson = M["Lesson"]
    Teacher = M["Teacher"]
    Homework = M["Homework"]
    HAS_HOMEWORK = Homework is not None

    if not all([TimeSlot, Lesson, Teacher]):
        # нет критичных моделей — отдадим пустой ответ
        today = _date.today()
        dow = today.weekday()
        date_from = today - _td(days=dow)
        date_to = date_from + _td(days=6)
        return jsonify({
            "teacher": teacher_ref,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "lessons": [],
            "stats": {"total_days": 0, "total_lessons": 0, "total_hours": 0.0}
        })

    from_str = (request.args.get("from") or "").strip()
    to_str = (request.args.get("to") or "").strip()
    today = _date.today()

    def _parse(d):
        try:
            return _dt.strptime(d, "%Y-%m-%d").date()
        except Exception:
            return None

    date_from = _parse(from_str)
    date_to = _parse(to_str)
    if not date_from or not date_to or date_from > date_to:
        dow = today.weekday()  # 0=Mon
        date_from = today - _td(days=dow)
        date_to = date_from + _td(days=6)

    # найти преподавателя
    teacher = None
    if teacher_ref.isdigit():
        teacher = db.session.get(Teacher, int(teacher_ref))
    if not teacher:
        teacher = (
            db.session.query(Teacher)
            .filter(func.lower(Teacher.full_name) == teacher_ref.lower())
            .first()
        ) or (
            db.session.query(Teacher)
            .filter(func.lower(Teacher.full_name).like(f"%{teacher_ref.lower()}%"))
            .first()
        )
    if not teacher:
        return jsonify({
            "teacher": teacher_ref,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "lessons": [],
            "stats": {"total_days": 0, "total_lessons": 0, "total_hours": 0.0}
        })

    # сетка слотов -> для длительности
    order_col = getattr(TimeSlot, "order_no", None) or getattr(TimeSlot, "order", None) or getattr(TimeSlot, "id")
    slots = db.session.query(TimeSlot).order_by(order_col.asc()).all()
    slots_map = {}
    for s in slots:
        start = _to_minutes(getattr(s, "start_time", getattr(s, "start", None)))
        end = _to_minutes(getattr(s, "end_time", getattr(s, "end", None)))
        ord_no = getattr(s, "order_no", getattr(s, "order", getattr(s, "id", None)))
        if ord_no is not None and start is not None and end is not None:
            slots_map[int(ord_no)] = (start, end)

    rows = (
        db.session.query(Lesson)
        .options(
            joinedload(Lesson.subject),
            joinedload(Lesson.teacher),
            joinedload(Lesson.room),
            joinedload(Lesson.lesson_type),
            joinedload(Lesson.time_slot),
        )
        .filter(
            getattr(Lesson, "teacher_id") == getattr(teacher, "id"),
            getattr(Lesson, "date") >= date_from,
            getattr(Lesson, "date") <= date_to,
        )
        .order_by(getattr(Lesson, "date").asc(), getattr(Lesson, "order_no").asc())
        .all()
    )

    lessons = []
    total_minutes = 0
    days_with_lessons = set()

    for l in rows:
        ts_rel = getattr(l, "time_slot", None)
        if ts_rel:
            start_hm = _to_hhmm(getattr(ts_rel, "start_time", getattr(ts_rel, "start", None)))
            end_hm = _to_hhmm(getattr(ts_rel, "end_time", getattr(ts_rel, "end", None)))
            order_no = getattr(ts_rel, "order_no", getattr(ts_rel, "order", None))
        else:
            start_hm = _to_hhmm(getattr(l, "start_time", None))
            end_hm = _to_hhmm(getattr(l, "end_time", None))
            order_no = getattr(l, "order_no", None)

        s_min = _to_minutes(start_hm)
        e_min = _to_minutes(end_hm)
        if (s_min is None or e_min is None) and isinstance(order_no, int) and order_no in slots_map:
            s_min, e_min = slots_map[order_no]
            start_hm = start_hm or f"{s_min // 60:02d}:{s_min % 60:02d}"
            end_hm = end_hm or f"{e_min // 60:02d}:{e_min % 60:02d}"

        dur = (e_min - s_min) if (s_min is not None and e_min is not None and e_min >= s_min) else 0
        total_minutes += dur

        subj = getattr(l, "subject", None)
        subj_name = getattr(subj, "name", "Дисциплина") if subj else "Дисциплина"

        tch = getattr(l, "teacher", None)
        teacher_full = "Преподаватель"
        if tch:
            teacher_full = getattr(tch, "full_name", None) or " ".join(
                [getattr(tch, "last_name", ""), getattr(tch, "first_name", ""), getattr(tch, "middle_name", "")]
            ).strip() or "Преподаватель"

        room = getattr(l, "room", None)
        room_number = getattr(room, "number", None) if room else None

        lt = getattr(l, "lesson_type", None)
        type_name = getattr(lt, "name", "Занятие") if lt else "Занятие"

        hw_text = None
        if HAS_HOMEWORK:
            hw_rel = getattr(l, "homework", None)
            if hw_rel and getattr(hw_rel, "text", None):
                hw_text = hw_rel.text
            else:
                hws = getattr(l, "homeworks", None)
                if hws and len(hws) and getattr(hws[0], "text", None):
                    hw_text = hws[0].text

        days_with_lessons.add(getattr(l, "date"))
        lessons.append({
            "date": getattr(l, "date").isoformat(),
            "is_break": False,
            "subject": {"name": subj_name},
            "teacher": {"full_name": teacher_full},
            "time_slot": {
                "order_no": order_no,
                "start_time": start_hm,
                "end_time": end_hm,
            },
            "room": {"number": room_number} if room_number else None,
            "lesson_type": {"name": type_name},
            "is_remote": bool(getattr(l, "is_remote", False)),
            "homework": {"text": hw_text} if hw_text else None,
        })

    stats = {
        "total_days": len(days_with_lessons),
        "total_lessons": len(lessons),
        "total_hours": round(total_minutes / 60.0, 2),
    }

    return jsonify({
        "teacher": getattr(teacher, "full_name", teacher_ref),
        "teacher_id": getattr(teacher, "id"),
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "lessons": lessons,
        "stats": stats
    })
