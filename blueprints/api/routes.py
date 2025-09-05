from datetime import date, datetime, timedelta
from flask import jsonify, request
from sqlalchemy import or_, func

from . import bp
from extensions import db

# Модели (импортируем прямые имена — без «lessons» и прочих вариантов)
from models.group import Group
from models.teacher import Teacher
from models.subject import Subject
from models.lesson import Lesson
from models.timeslot import TimeSlot
from models.room import Room  # опционально
from models.lesson_type import LessonType  # опционально
from models.homework import Homework  # опционально


# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------

def _parse_iso_date(s: str | None) -> date:
    if not s:
        return date.today()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return date.today()


def _week_range(any_day: date) -> tuple[date, date]:
    # понедельник..воскресенье
    start = any_day - timedelta(days=any_day.weekday())
    end = start + timedelta(days=6)
    return start, end


def _slot_of(lesson: Lesson) -> TimeSlot | None:
    # 1) связь lesson.time_slot, 2) по FK, 3) None
    try:
        if hasattr(lesson, "time_slot") and lesson.time_slot:
            return lesson.time_slot
    except Exception:
        pass
    ts_id = getattr(lesson, "time_slot_id", None)
    if ts_id:
        try:
            return db.session.get(TimeSlot, ts_id)
        except Exception:
            return None
    return None


def _order_of(lesson: Lesson) -> int | None:
    # поддерживаем и order_no, и order
    if hasattr(lesson, "order_no") and getattr(lesson, "order_no") is not None:
        return int(getattr(lesson, "order_no"))
    if hasattr(lesson, "order") and getattr(lesson, "order") is not None:
        return int(getattr(lesson, "order"))
    ts = _slot_of(lesson)
    if ts is not None:
        if hasattr(ts, "order_no") and ts.order_no is not None:
            return int(ts.order_no)
        if hasattr(ts, "order") and ts.order is not None:
            return int(ts.order)
    return None


def _time_bounds(lesson: Lesson) -> tuple[str | None, str | None]:
    # приоритет: slot.start/end -> собственные поля -> None
    ts = _slot_of(lesson)
    st = None
    en = None
    if ts is not None:
        st = getattr(ts, "start_time", None)
        en = getattr(ts, "end_time", None)
    if st is None:
        st = getattr(lesson, "start_time", None)
    if en is None:
        en = getattr(lesson, "end_time", None)
    # привести к "HH:MM"
    def fmt(t):
        if t is None:
            return None
        if isinstance(t, str):
            return t[:5]
        try:
            return f"{t.hour:02d}:{t.minute:02d}"
        except Exception:
            return None
    return fmt(st), fmt(en)


def _teacher_name(lesson: Lesson) -> str:
    t = getattr(lesson, "teacher", None)
    if t and getattr(t, "full_name", None):
        return t.full_name
    # запасной путь: заглушка
    tid = getattr(lesson, "teacher_id", None)
    if tid:
        t = db.session.get(Teacher, tid)
        if t and getattr(t, "full_name", None):
            return t.full_name
    return ""


def _subject_name(lesson: Lesson) -> str:
    s = getattr(lesson, "subject", None)
    if s and getattr(s, "name", None):
        return s.name
    sid = getattr(lesson, "subject_id", None)
    if sid:
        s = db.session.get(Subject, sid)
        if s and getattr(s, "name", None):
            return s.name
    # некоторые модели используют title
    if s and getattr(s, "title", None):
        return s.title or ""
    return ""


def _room_stub(lesson: Lesson) -> dict | None:
    r = getattr(lesson, "room", None)
    if r:
        return {"id": getattr(r, "id", None), "number": getattr(r, "number", None)}
    rid = getattr(lesson, "room_id", None)
    if rid:
        r = db.session.get(Room, rid)
        if r:
            return {"id": getattr(r, "id", None), "number": getattr(r, "number", None)}
    return None


def _lesson_type_name(lesson: Lesson) -> str | None:
    lt = getattr(lesson, "lesson_type", None)
    if lt and getattr(lt, "name", None):
        return lt.name
    ltid = getattr(lesson, "lesson_type_id", None)
    if ltid:
        lt = db.session.get(LessonType, ltid)
        if lt and getattr(lt, "name", None):
            return lt.name
    return None


def _homework_text(lesson: Lesson) -> str | None:
    hw = getattr(lesson, "homework", None)
    if hw and getattr(hw, "text", None):
        return hw.text
    # если связь другая — пробуем поискать по lesson_id
    try:
        q = db.session.query(Homework).filter(getattr(Homework, "lesson_id") == getattr(lesson, "id"))
        hw = q.first()
        if hw and getattr(hw, "text", None):
            return hw.text
    except Exception:
        pass
    return None


def _serialize_lesson(lesson: Lesson) -> dict:
    start, end = _time_bounds(lesson)
    is_remote = bool(
        getattr(lesson, "is_remote", False)
        or getattr(lesson, "remote", False)
        or getattr(lesson, "online", False)
    )
    return {
        "id": getattr(lesson, "id", None),
        "date": str(getattr(lesson, "date", getattr(lesson, "lesson_date", getattr(lesson, "day", None)))),
        "time_slot": {
            "order_no": _order_of(lesson),
            "start_time": start,
            "end_time": end,
        },
        "subject": {"name": _subject_name(lesson)},
        "teacher": {"full_name": _teacher_name(lesson)},
        "room": _room_stub(lesson),
        "lesson_type": {"name": _lesson_type_name(lesson)} if _lesson_type_name(lesson) else None,
        "is_remote": is_remote,
        "homework": {"text": _homework_text(lesson)} if _homework_text(lesson) else None,
        "is_break": False,
    }


def _insert_breaks(sorted_items: list[dict]) -> list[dict]:
    """Вставляет «перерыв» между неплотно идущими парами того же дня."""
    out = []
    prev_end = None
    for it in sorted_items:
        st = it["time_slot"]["start_time"]
        if prev_end and st and prev_end != st:
            out.append({
                "is_break": True,
                "from": prev_end,
                "to": st,
            })
        out.append(it)
        prev_end = it["time_slot"]["end_time"]
    return out


# ---------- SUGGEST ----------

@bp.get("/suggest")
def suggest():
    q = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit") or 10), 25)

    if not q:
        return jsonify({"items": []})

    items = []

    # Группы: code / name
    try:
        g_rows = (
            db.session.query(Group)
            .filter(
                or_(
                    func.lower(Group.code).like(f"%{q.lower()}%"),
                    func.lower(getattr(Group, "name", Group.code)).like(f"%{q.lower()}%")
                )
            )
            .order_by(Group.code.asc())
            .limit(limit)
            .all()
        )
        for g in g_rows:
            items.append({
                "type": "group",
                "id": g.id,
                "code": getattr(g, "code", ""),
                "label": f"{getattr(g, 'code', '')} — группа"
            })
    except Exception:
        pass

    # Преподаватели: full_name/ФИО
    try:
        t_rows = (
            db.session.query(Teacher)
            .filter(
                or_(
                    func.lower(getattr(Teacher, "full_name", "")).like(f"%{q.lower()}%"),
                    func.lower(getattr(Teacher, "last_name", "")).like(f"%{q.lower()}%"),
                    func.lower(getattr(Teacher, "first_name", "")).like(f"%{q.lower()}%"),
                    func.lower(getattr(Teacher, "middle_name", "")).like(f"%{q.lower()}%")
                )
            )
            .order_by(getattr(Teacher, "full_name", getattr(Teacher, "last_name", "id")).asc())
            .limit(limit)
            .all()
        )
        for t in t_rows:
            label = getattr(t, "full_name", None) or " ".join(
                filter(None, [getattr(t, "last_name", ""), getattr(t, "first_name", ""), getattr(t, "middle_name", "")])
            ).strip()
            items.append({"type": "teacher", "id": t.id, "label": f"{label} — преподаватель"})
    except Exception:
        pass

    # Дисциплины: name/title
    try:
        s_rows = (
            db.session.query(Subject)
            .filter(
                or_(
                    func.lower(getattr(Subject, "name", "")).like(f"%{q.lower()}%"),
                    func.lower(getattr(Subject, "title", "")).like(f"%{q.lower()}%")
                )
            )
            .order_by(getattr(Subject, "name", getattr(Subject, "title", "id")).asc())
            .limit(limit)
            .all()
        )
        for s in s_rows:
            label = getattr(s, "name", None) or getattr(s, "title", "")
            items.append({"type": "subject", "id": s.id, "label": f"{label} — дисциплина"})
    except Exception:
        pass

    return jsonify({"items": items})


# ---------- SCHEDULE (GROUP) ----------

@bp.get("/schedule/group/<string:code>")
def schedule_group(code: str):
    """
    GET /api/v1/schedule/group/<code>?date=YYYY-MM-DD&range=day|week
    Ответ:
      range=day  -> {"lessons":[...]}
      range=week -> {"days":[{"date":"YYYY-MM-DD","lessons":[...]}]}
    """
    code = code.strip()
    d = _parse_iso_date(request.args.get("date"))
    mode = (request.args.get("range") or "day").lower().strip()
    if mode not in {"day", "week"}:
        mode = "day"

    group = (
        db.session.query(Group)
        .filter(func.lower(Group.code) == code.lower())
        .first()
    )
    if not group:
        return jsonify({"error": "group_not_found", "code": code}), 404

    def _lesson_date_col():
        # поддерживаем разные имена у столбца даты
        if hasattr(Lesson, "date"):
            return Lesson.date
        if hasattr(Lesson, "lesson_date"):
            return Lesson.lesson_date
        if hasattr(Lesson, "day"):
            return Lesson.day
        # fallback: всё равно фильтруем позже в Python (хуже, но безопасно)
        return None

    date_col = _lesson_date_col()

    def _base_q():
        q = db.session.query(Lesson)
        # group_id
        if hasattr(Lesson, "group_id"):
            q = q.filter(Lesson.group_id == group.id)
        elif hasattr(Lesson, "group"):
            q = q.filter(Lesson.group == group)
        # по возможности — SQL-фильтр по дате, иначе дальше в Python
        if date_col is not None:
            return q, True
        return q, False

    if mode == "day":
        q, has_sql_date = _base_q()
        if has_sql_date:
            q = q.filter(date_col == d)
        rows = q.all()
        if not has_sql_date:
            # отфильтровать вручную, если нет явной колонки
            rows = [x for x in rows if (getattr(x, "date", getattr(x, "lesson_date", getattr(x, "day", None))) == d)]
        # сортировка
        ser = sorted((_serialize_lesson(x) for x in rows), key=lambda it: (it["time_slot"]["order_no"] or 999, it["time_slot"]["start_time"] or "99:99"))
        ser = _insert_breaks(ser)
        return jsonify({"lessons": ser})

    # week
    start, end = _week_range(d)
    q, has_sql_date = _base_q()
    if has_sql_date:
        q = q.filter(date_col >= start, date_col <= end)
    rows = q.all()
    if not has_sql_date:
        rows = [x for x in rows if start <= (getattr(x, "date", getattr(x, "lesson_date", getattr(x, "day", date.min)))) <= end]

    # сгруппировать по дате
    buckets: dict[date, list] = {}
    for x in rows:
        dx = getattr(x, "date", getattr(x, "lesson_date", getattr(x, "day", None)))
        if not isinstance(dx, date):
            continue
        buckets.setdefault(dx, []).append(_serialize_lesson(x))

    days_out = []
    cur = start
    while cur <= end:
        day_lessons = sorted(buckets.get(cur, []), key=lambda it: (it["time_slot"]["order_no"] or 999, it["time_slot"]["start_time"] or "99:99"))
        day_lessons = _insert_breaks(day_lessons)
        days_out.append({"date": cur.isoformat(), "lessons": day_lessons})
        cur += timedelta(days=1)

    return jsonify({"days": days_out})
