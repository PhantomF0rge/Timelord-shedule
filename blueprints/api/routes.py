from flask import Blueprint, jsonify, request, abort
from datetime import date, datetime, timedelta

from extensions import db

# Стабильные импорты (без "умных" кандидатов)
from models import Group, Teacher, Subject, Lesson, TimeSlot  # Room/LessonType/Homework будем брать через отношения, не обязательно импортить

bp = Blueprint("api", __name__)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------

def _parse_date(dstr: str | None) -> date:
    if not dstr:
        return date.today()
    try:
        return datetime.strptime(dstr, "%Y-%m-%d").date()
    except Exception:
        return date.today()

def _monday_sunday(any_day: date) -> tuple[date, date]:
    monday = any_day - timedelta(days=any_day.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def _get_lesson_date(l) -> date | None:
    # поддержка разных схем: date / lesson_date / day
    for attr in ("date", "lesson_date", "day"):
        if hasattr(l, attr):
            return getattr(l, attr)
    return None

def _get_slot(l) -> dict:
    """
    Возвращает словарь со слотом:
    { start_time: "HH:MM", end_time: "HH:MM", order_no: int }
    Берёт либо из Lesson.start_time/end_time/order_no, либо из l.time_slot.*
    """
    def to_hhmm(t):
        if t is None:
            return None
        return f"{int(t.hour):02d}:{int(t.minute):02d}"

    # 1) прямые поля урока
    start = getattr(l, "start_time", None)
    end = getattr(l, "end_time", None)
    order = getattr(l, "order_no", None)
    if order is None:
        order = getattr(l, "order", None)

    # 2) попробовать через relation time_slot
    ts = getattr(l, "time_slot", None)
    if ts is not None:
        if start is None and hasattr(ts, "start_time"):
            start = getattr(ts, "start_time")
        if end is None and hasattr(ts, "end_time"):
            end = getattr(ts, "end_time")
        if order is None:
            order = getattr(ts, "order_no", None)
            if order is None:
                order = getattr(ts, "order", None)

    return {
        "start_time": to_hhmm(start),
        "end_time": to_hhmm(end),
        "order_no": order if isinstance(order, int) or (isinstance(order, str) and order.isdigit()) else None
    }

def _teacher_name(l) -> str:
    t = getattr(l, "teacher", None)
    if not t:
        return ""
    # пробуем full_name; если нет — собираем из Ф/И/О
    fn = getattr(t, "full_name", None)
    if fn:
        return fn
    parts = [getattr(t, "last_name", None), getattr(t, "first_name", None), getattr(t, "middle_name", None)]
    return " ".join([p for p in parts if p])

def _subject_name(l) -> str:
    s = getattr(l, "subject", None)
    if not s:
        return ""
    return getattr(s, "name", None) or getattr(s, "title", "") or ""

def _lesson_type_name(l) -> str:
    lt = getattr(l, "lesson_type", None)
    if not lt:
        return ""
    return getattr(lt, "name", None) or getattr(lt, "title", "") or ""

def _room_dict(l):
    r = getattr(l, "room", None)
    if not r:
        return None
    return {
        "number": getattr(r, "number", None),
        "capacity": getattr(r, "capacity", None),
    }

def _homework_dict(l):
    # поддержим разные варианты: lesson.homeworks (list), lesson.homework (obj/string)
    if hasattr(l, "homeworks"):
        try:
            hw = next(iter(getattr(l, "homeworks")))
            if hw is None:
                return None
            if hasattr(hw, "text"):
                return {"text": hw.text}
            if isinstance(hw, str):
                return {"text": hw}
        except StopIteration:
            pass
    if hasattr(l, "homework"):
        hw = getattr(l, "homework")
        if hasattr(hw, "text"):
            return {"text": hw.text}
        if isinstance(hw, str):
            return {"text": hw}
    return None

def _is_remote(l) -> bool:
    for flag in ("is_remote", "remote", "online"):
        if hasattr(l, flag):
            try:
                return bool(getattr(l, flag))
            except Exception:
                pass
    return False

def _lesson_to_json(l):
    slot = _get_slot(l)
    return {
        "is_break": False,
        "time_slot": {
            "start_time": slot["start_time"] or "",
            "end_time":   slot["end_time"] or "",
            "order_no":   slot["order_no"] or 0,
        },
        "subject": {"name": _subject_name(l)},
        "teacher": {"full_name": _teacher_name(l)},
        "room": _room_dict(l),
        "lesson_type": {"name": _lesson_type_name(l)},
        "homework": _homework_dict(l),
        "is_remote": _is_remote(l),
    }

def _insert_breaks(sorted_items: list[dict]) -> list[dict]:
    """
    Между отсортированными по order_no/времени занятиями вставляет «перерывы»,
    когда между соседними слотами есть зазор.
    """
    out = []
    prev_end = None
    for item in sorted_items:
        start = item["time_slot"]["start_time"]
        end   = item["time_slot"]["end_time"]
        if prev_end and start and end and start > prev_end:
            out.append({
                "is_break": True,
                "from": prev_end,
                "to": start
            })
        out.append(item)
        prev_end = end or prev_end
    return out

def _order_key(js: dict):
    # сначала по номеру пары, затем по времени старта как fallback
    o = js["time_slot"].get("order_no") or 0
    start = js["time_slot"].get("start_time") or ""
    return (int(o) if isinstance(o, int) or (isinstance(o, str) and str(o).isdigit()) else 0, start)

# ---------- ENDPOINTS ----------

@bp.get("/suggest")
def suggest():
    """
    Подсказки для поиска: группы / преподаватели / дисциплины
    GET /api/v1/suggest?q=...&limit=10
    """
    q = (request.args.get("q") or "").strip().lower()
    limit = int(request.args.get("limit") or 10)
    items = []

    if q:
        # GROUPS
        if Group is not None:
            query = db.session.query(Group)
            if hasattr(Group, "code"):
                query = query.filter(db.func.lower(Group.code).like(f"%{q}%"))
            if hasattr(Group, "name"):
                query = query.union(
                    db.session.query(Group).filter(db.func.lower(Group.name).like(f"%{q}%"))
                )
            query = query.order_by(getattr(Group, "code", Group.id).asc()).limit(limit)
            for g in query.all():
                items.append({
                    "type": "group",
                    "id": getattr(g, "id", None),
                    "code": getattr(g, "code", None),
                    "label": getattr(g, "name", None) or getattr(g, "code", None) or "Группа"
                })

        # TEACHERS
        if Teacher is not None:
            query = db.session.query(Teacher)
            if hasattr(Teacher, "full_name"):
                query = query.filter(db.func.lower(Teacher.full_name).like(f"%{q}%"))
            else:
                # по частям ФИО
                ors = []
                for part in ("last_name", "first_name", "middle_name"):
                    if hasattr(Teacher, part):
                        ors.append(db.func.lower(getattr(Teacher, part)).like(f"%{q}%"))
                if ors:
                    query = query.filter(db.or_(*ors))
            query = query.order_by(getattr(Teacher, "id").asc()).limit(limit)
            for t in query.all():
                items.append({
                    "type": "teacher",
                    "id": getattr(t, "id", None),
                    "label": getattr(t, "full_name", None) or _teacher_name(type("X", (), {"teacher": t})) or "Преподаватель"
                })

        # SUBJECTS
        if Subject is not None:
            query = db.session.query(Subject)
            field = "name" if hasattr(Subject, "name") else ("title" if hasattr(Subject, "title") else None)
            if field:
                query = query.filter(db.func.lower(getattr(Subject, field)).like(f"%{q}%"))
                query = query.order_by(getattr(Subject, field).asc()).limit(limit)
                for s in query.all():
                    items.append({
                        "type": "subject",
                        "id": getattr(s, "id", None),
                        "label": getattr(s, "name", None) or getattr(s, "title", None) or "Дисциплина"
                    })

    return jsonify({"items": items})


@bp.get("/schedule/group/<code>")
def schedule_group(code: str):
    """
    Расписание по коду группы.
    Параметры:
      date=YYYY-MM-DD (по умолчанию сегодня)
      range=day|week   (по умолчанию day)

    Формат (day):
      { lessons: [ normalized-lesson-or-break ] }

    Формат (week):
      { days: [ {date: "YYYY-MM-DD", lessons: [...]}, ... ] }
    """
    if Group is None or Lesson is None:
        abort(500, "Models not available")

    qdate = _parse_date(request.args.get("date"))
    rng = (request.args.get("range") or "day").lower()

    # найти группу
    gq = db.session.query(Group)
    if hasattr(Group, "code"):
        gq = gq.filter(db.func.lower(Group.code) == code.lower())
    else:
        gq = gq.filter(Group.id == -1)  # заглушка, чтобы ничего не вернуть, если совсем нет поля
    group = gq.first()
    if not group:
        return jsonify({"lessons": []}) if rng == "day" else jsonify({"days": []})

    # строим базовый Query по Lesson
    L = db.session.query(Lesson)
    # по группе
    if hasattr(Lesson, "group_id") and hasattr(group, "id"):
        L = L.filter(Lesson.group_id == group.id)

    # по дате / диапазону
    # выбираем актуальное поле даты в модели
    date_field = None
    for attr in ("date", "lesson_date", "day"):
        if hasattr(Lesson, attr):
            date_field = getattr(Lesson, attr)
            break

    if rng == "day":
        if date_field is not None:
            L = L.filter(date_field == qdate)
        lessons = L.all()
        # пост-фильтр на всякий случай (если не удалось отфильтровать в SQL)
        out = []
        for l in lessons:
            d = _get_lesson_date(l)
            if d and d != qdate:
                continue
            out.append(_lesson_to_json(l))

        out.sort(key=_order_key)
        out = _insert_breaks(out)
        return jsonify({"lessons": out})

    # week
    monday, sunday = _monday_sunday(qdate)
    lessons = []
    if date_field is not None:
        Lw = L.filter(date_field >= monday, date_field <= sunday)
        lessons = Lw.all()
    else:
        lessons = L.all()

    # сгруппируем по дате, отсортируем внутри дня, вставим перерывы
    box: dict[str, list[dict]] = {}
    for l in lessons:
        d = _get_lesson_date(l)
        if d is None:
            continue
        if not (monday <= d <= sunday):
            continue
        js = _lesson_to_json(l)
        box.setdefault(d.isoformat(), []).append(js)

    days = []
    cur = monday
    while cur <= sunday:
        arr = box.get(cur.isoformat(), [])
        arr.sort(key=_order_key)
        arr = _insert_breaks(arr)
        days.append({"date": cur.isoformat(), "lessons": arr})
        cur += timedelta(days=1)

    return jsonify({"days": days})
