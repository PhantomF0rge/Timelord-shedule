from flask import request, jsonify
from sqlalchemy import func, or_
from sqlalchemy.exc import OperationalError, ProgrammingError, DatabaseError
from . import bp
from extensions import db

# Пытаемся импортировать реальные модели; если их нет/другие имена — оставим None.
try:
    from models.group import Group
except Exception:
    Group = None

try:
    from models.teacher import Teacher
except Exception:
    Teacher = None

try:
    from models.subject import Subject
except Exception:
    Subject = None


def _like(field, q: str):
    """Кросс-СУБД CASE-INSENSITIVE like."""
    return func.lower(field).like(f"%{q.lower()}%")

def _collect_group(q: str, limit: int):
    items = []
    if not Group:
        return items
    code_col = getattr(Group, "code", None)
    name_col = getattr(Group, "name", None)
    label_col = getattr(Group, "label", None)

    filters = []
    if code_col is not None:
        filters.append(_like(code_col, q))
    if name_col is not None:
        filters.append(_like(name_col, q))
    if label_col is not None:
        filters.append(_like(label_col, q))
    if not filters:
        return items

    try:
        query = (
            db.session.query(Group)
            .filter(or_(*filters))
            .order_by(*(c.asc() for c in [code_col or name_col] if c is not None))
            .limit(limit)
        )
        rows = query.all()
    except (OperationalError, ProgrammingError, DatabaseError):
        # БД/таблиц ещё нет — вернём пусто, чтобы не падал фронт
        return []

    for g in rows:
        code = getattr(g, "code", None)
        name = getattr(g, "name", None)
        label = getattr(g, "label", None)
        items.append({
            "type": "group",
            "id": getattr(g, "id", None),
            "label": name or label or code or "Группа",
            "code": code or (name or label),
        })
    return items

def _teacher_fullname(t) -> str:
    fn = getattr(t, "full_name", None)
    if fn:
        return fn
    parts = [getattr(t, n, "") for n in ("last_name", "first_name", "middle_name")]
    return " ".join(p for p in parts if p).strip() or "Преподаватель"

def _collect_teacher(q: str, limit: int):
    items = []
    if not Teacher:
        return items
    fields = []
    for attr in ("full_name", "last_name", "first_name", "middle_name"):
        col = getattr(Teacher, attr, None)
        if col is not None:
            fields.append(col)
    if not fields:
        return items
    filters = [_like(col, q) for col in fields]
    try:
        query = db.session.query(Teacher).filter(or_(*filters)).limit(limit)
        rows = query.all()
    except (OperationalError, ProgrammingError, DatabaseError):
        return []
    for t in rows:
        items.append({
            "type": "teacher",
            "id": getattr(t, "id", None),
            "label": _teacher_fullname(t)
        })
    return items

def _collect_subject(q: str, limit: int):
    items = []
    if not Subject:
        return items
    name_col = getattr(Subject, "name", None)
    title_col = getattr(Subject, "title", None)
    field = name_col or title_col
    if field is None:
        return items
    try:
        query = db.session.query(Subject).filter(_like(field, q)).limit(limit)
        rows = query.all()
    except (OperationalError, ProgrammingError, DatabaseError):
        return []
    for s in rows:
        items.append({
            "type": "subject",
            "id": getattr(s, "id", None),
            "label": getattr(s, "name", None) or getattr(s, "title", None) or "Дисциплина"
        })
    return items

# ---------- SUGGEST (из БД с fallback'ом) ----------

@bp.get("/suggest")
def suggest():
    """
    GET /api/v1/suggest?q=&type=group|teacher|subject&limit=10
    Ищет по БД. Если таблиц ещё нет — не падаем, возвращаем пустой список или моки.
    """
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 10)
    only_type = (request.args.get("type") or "").strip().lower()

    if not q:
        return jsonify({"items": []})

    try:
        items = []
        if not only_type or only_type == "group":
            items += _collect_group(q, limit)
        if (not only_type or only_type == "teacher") and len(items) < limit:
            items += _collect_teacher(q, limit - len(items))
        if (not only_type or only_type == "subject") and len(items) < limit:
            items += _collect_subject(q, limit - len(items))
        return jsonify({"items": items[:limit]})
    except Exception:
        # запасной план — небольшие моки для UX
        mocks = [
            {"type":"group","id":1,"label":"ПИ-101","code":"PI-101"},
            {"type":"group","id":2,"label":"ИС-202","code":"IS-202"},
            {"type":"teacher","id":101,"label":"Иванов И.И."},
            {"type":"subject","id":201,"label":"Программирование"},
        ]
        ql = q.lower()
        filtered = [m for m in mocks if ql in m["label"].lower() or ql in m.get("code","").lower()]
        return jsonify({"items": filtered[:limit]})


# ---------- SCHEDULE (пока прежний мок — заменим следующим шагом) ----------

@bp.get("/schedule/group/<code>")
def schedule_group(code: str):
    """
    GET /api/v1/schedule/group/<code>?date=YYYY-MM-DD&range=day|week
    Возвращает занятия на день с автоматической вставкой «перерывов» по полной сетке TimeSlot.
    """
    from datetime import date as _date, datetime as _dt
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func
    from .services.schedule_utils import insert_breaks, normalize_slot
    from extensions import db

    # импорт моделей
    from models.group import Group
    from models.timeslot import TimeSlot
    from models.lesson import Lesson
    from models.subject import Subject
    from models.teacher import Teacher
    from models.room import Room
    from models.lesson_type import LessonType
    # домашка может отсутствовать в схеме — обрабатываем мягко
    try:
        from models.homework import Homework  # noqa: F401
        HAS_HOMEWORK = True
    except Exception:
        HAS_HOMEWORK = False

    # --- параметры ---
    date_str = (request.args.get("date") or "").strip()
    try:
        target_date = _dt.strptime(date_str, "%Y-%m-%d").date() if date_str else _date.today()
    except Exception:
        target_date = _date.today()

    # --- находим группу по коду (без регистра) ---
    group = (
        db.session.query(Group)
        .filter(func.lower(Group.code) == code.lower())
        .first()
    )
    if not group:
        # частичное совпадение (на всякий случай)
        group = (
            db.session.query(Group)
            .filter(func.lower(Group.code).like(f"%{code.lower()}%"))
            .first()
        )
    if not group:
        return jsonify({"group_code": code, "date": target_date.isoformat(), "lessons": []})

    # --- сетка слотов ---
    slots = db.session.query(TimeSlot).order_by(TimeSlot.order_no.asc()).all()

    # --- занятия на день текущей группы ---
    # делаем prefetch связей, чтобы избежать N+1
    q = (
        db.session.query(Lesson)
        .options(
            joinedload(Lesson.subject),
            joinedload(Lesson.teacher),
            joinedload(Lesson.room),
            joinedload(Lesson.lesson_type),
            joinedload(Lesson.time_slot),
        )
        .filter(
            Lesson.group_id == group.id,
            Lesson.date == target_date
        )
        .order_by(
            Lesson.order_no.asc()
        )
    )
    rows = q.all()

    # --- сбор JSON ---
    def _to_hhmm(v):
        if v is None:
            return None
        if isinstance(v, str):
            return v[:5]
        try:
            return v.strftime("%H:%M")
        except Exception:
            return str(v)[:5]

    payload = []
    for l in rows:
        # timeslot
        if l.time_slot:
            ts = {
                "order_no": l.time_slot.order_no,
                "start_time": _to_hhmm(l.time_slot.start_time),
                "end_time": _to_hhmm(l.time_slot.end_time),
            }
        else:
            ts = {
                "order_no": l.order_no,
                "start_time": _to_hhmm(getattr(l, "start_time", None)),
                "end_time": _to_hhmm(getattr(l, "end_time", None)),
            }

        # subject
        subj_name = l.subject.name if l.subject else "Дисциплина"

        # teacher
        if l.teacher and getattr(l.teacher, "full_name", None):
            teacher_full = l.teacher.full_name
        elif l.teacher:
            parts = [getattr(l.teacher, "last_name", ""), getattr(l.teacher, "first_name", ""), getattr(l.teacher, "middle_name", "")]
            teacher_full = " ".join([p for p in parts if p]).strip() or "Преподаватель"
        else:
            teacher_full = "Преподаватель"

        # room
        room_number = l.room.number if l.room else None

        # type
        type_name = l.lesson_type.name if l.lesson_type else "Занятие"

        # homework (если есть отношение l.homework или l.homeworks[0])
        hw_text = None
        if HAS_HOMEWORK:
            hw_rel = getattr(l, "homework", None)
            if hw_rel and getattr(hw_rel, "text", None):
                hw_text = hw_rel.text
            else:
                # если связь списочная (homeworks)
                hws = getattr(l, "homeworks", None)
                if hws and len(hws) > 0 and getattr(hws[0], "text", None):
                    hw_text = hws[0].text

        payload.append({
            "is_break": False,
            "subject": {"name": subj_name},
            "teacher": {"full_name": teacher_full},
            "time_slot": ts,
            "room": {"number": room_number} if room_number else None,
            "lesson_type": {"name": type_name},
            "is_remote": bool(getattr(l, "is_remote", False)),
            "homework": {"text": hw_text} if hw_text else None,
        })

    # --- вставляем «перерывы» и возвращаем ---
    payload = insert_breaks(slots, payload)
    return jsonify({
        "group_code": group.code,
        "date": target_date.isoformat(),
        "lessons": payload
    })