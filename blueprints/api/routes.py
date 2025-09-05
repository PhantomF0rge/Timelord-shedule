from flask import Blueprint, jsonify, request
from sqlalchemy import func, and_
from datetime import datetime, timedelta, date as date_cls

from extensions import db

bp = Blueprint("api", __name__)

# ----- безопасные импорты моделей с синонимами имён файлов -----
def _import_model(candidates):
    last_err = None
    for module_path, name in candidates:
        try:
            mod = __import__(module_path, fromlist=[name])
            return getattr(mod, name)
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err

# Базовые справочники
Group = _import_model([
    ("models.group", "Group"),
    ("models.groups", "Group"),
])
Teacher = _import_model([
    ("models.teacher", "Teacher"),
    ("models.teachers", "Teacher"),
])
Subject = _import_model([
    ("models.subject", "Subject"),
    ("models.subjects", "Subject"),
])
LessonType = _import_model([
    ("models.lesson_type", "LessonType"),
    ("models.lessontype", "LessonType"),
])

# Аудитории/корпуса (опционально)
try:
    Room = _import_model([
        ("models.room", "Room"),
        ("models.rooms", "Room"),
    ])
except Exception:
    Room = None

# Временные слоты — имена часто расходятся
try:
    TimeSlot = _import_model([
        ("models.timeslot", "TimeSlot"),
        ("models.time_slot", "TimeSlot"),
        ("models.slot", "TimeSlot"),
    ])
except Exception:
    TimeSlot = None

# Занятия
Lesson = _import_model([
    ("models.lesson", "Lesson"),
    ("models.lessons", "Lesson"),
])

# Домашка (если есть)
try:
    Homework = _import_model([
        ("models.homework", "Homework"),
    ])
except Exception:
    Homework = None


# ----- HELPERS -----
def _first_attr(obj, names):
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return None

def _date_col():
    # подбираем фактическое поле даты в модели Lesson
    col = _first_attr(Lesson, ["date", "lesson_date", "day"])
    if col is None:
        raise RuntimeError("Lesson date column not found (date/lesson_date/day)")
    return col

def _order_col():
    # порядок пары может храниться в Lesson или в TimeSlot
    col = _first_attr(Lesson, ["order_no", "order"])
    if col is None and TimeSlot is not None:
        col = _first_attr(TimeSlot, ["order_no", "order"])
    return col

def _time_values(lesson, slot):
    """Вернёт (start_str, end_str, order_no_int) из Lesson/TimeSlot (куда что попало)."""
    def fmt(t):
        try:
            return t.strftime("%H:%M")
        except Exception:
            return t  # строка уже

    start = None
    end = None
    order_no = None

    # Вариант 1: время хранится в слоте
    if slot is not None:
        start = fmt(_first_attr(slot, ["start_time", "start"]))
        end   = fmt(_first_attr(slot, ["end_time", "end"]))
        order_no = _first_attr(slot, ["order_no", "order"])

    # Вариант 2: время в самой записи занятия
    if start is None:
        start = fmt(_first_attr(lesson, ["start_time", "start"]))
    if end is None:
        end = fmt(_first_attr(lesson, ["end_time", "end"]))
    if order_no is None:
        order_no = _first_attr(lesson, ["order_no", "order"])

    # в JSON лучше int/None
    try:
        order_no = int(order_no) if order_no is not None else None
    except Exception:
        pass
    return start, end, order_no

def _normalize_lesson(lesson, slot=None):
    """Приводим любой вариант модели к единому формату фронта."""
    # subject
    subj = getattr(lesson, "subject", None)
    subject_name = getattr(subj, "name", None) or getattr(subj, "title", None) \
                   or getattr(lesson, "subject_name", None) or getattr(lesson, "subject_title", None) \
                   or getattr(lesson, "subject", None)

    # teacher
    teacher = getattr(lesson, "teacher", None)
    teacher_full = getattr(teacher, "full_name", None) \
                   or getattr(lesson, "teacher_full_name", None) \
                   or getattr(lesson, "teacher_name", None)

    # lesson type
    ltype = getattr(lesson, "lesson_type", None)
    ltype_name = getattr(ltype, "name", None) or getattr(ltype, "title", None) \
                 or getattr(lesson, "lesson_type_name", None) or getattr(lesson, "type", None)

    # room
    room = getattr(lesson, "room", None)
    room_number = getattr(room, "number", None) or getattr(lesson, "room_number", None)

    # homework
    hw = None
    if Homework is not None:
        # связь может быть one-to-one/one-to-many — пробуем оба варианта
        maybe_hw = getattr(lesson, "homework", None)
        if maybe_hw is not None:
            text = getattr(maybe_hw, "text", None) or getattr(maybe_hw, "title", None) or str(maybe_hw)
            hw = {"text": text}

    is_remote = bool(_first_attr(lesson, ["is_remote", "remote", "online"]) or False)

    start, end, order_no = _time_values(lesson, slot)

    return {
        "is_break": False,
        "subject": {"name": subject_name or ""},
        "teacher": {"full_name": teacher_full or ""},
        "lesson_type": {"name": ltype_name or "Занятие"},
        "time_slot": {
            "start_time": start or "",
            "end_time": end or "",
            "order_no": order_no,
        },
        "room": ({"number": room_number} if room_number else None),
        "homework": hw,
        "is_remote": is_remote,
    }

def _insert_breaks(lessons):
    """Вставляет «перерывы», если между парами есть окно (по времени). lessons — уже отсортированный список нормализованных пар одного дня."""
    out = []
    prev_end = None
    for l in lessons:
        if prev_end and l["time_slot"]["start_time"] and prev_end < l["time_slot"]["start_time"]:
            out.append({
                "is_break": True,
                "from": prev_end,
                "to": l["time_slot"]["start_time"],
            })
        out.append(l)
        prev_end = l["time_slot"]["end_time"]
    return out


# ----- SUGGEST (typeahead) -----
@bp.get("/suggest")
def suggest():
    q = (request.args.get("q") or "").strip().lower()
    limit = min(int(request.args.get("limit", 10) or 10), 20)
    items = []

    if not q:
        return jsonify({"items": []})

    # groups
    code_col = _first_attr(Group, ["code", "name", "label"])
    name_col = _first_attr(Group, ["name", "label", "code"])
    if code_col is not None and name_col is not None:
        rs = (
            db.session.query(Group)
            .filter(
                func.lower(code_col).like(f"%{q}%") | func.lower(name_col).like(f"%{q}%")
            )
            .order_by(code_col.asc())
            .limit(limit)
            .all()
        )
        for g in rs:
            items.append({
                "type": "group",
                "id": getattr(g, "id", None),
                "code": getattr(g, "code", None) or getattr(g, "label", None) or getattr(g, "name", None),
                "label": getattr(g, "name", None) or getattr(g, "label", None) or getattr(g, "code", None),
            })

    # teachers
    t_name = _first_attr(Teacher, ["full_name", "last_name", "first_name"])
    if t_name is not None:
        rs = (
            db.session.query(Teacher)
            .filter(func.lower(t_name).like(f"%{q}%"))
            .order_by(t_name.asc())
            .limit(limit)
            .all()
        )
        for t in rs:
            items.append({
                "type": "teacher",
                "id": getattr(t, "id", None),
                "label": getattr(t, "full_name", None) or " ".join(
                    [getattr(t, "last_name", "") or "", getattr(t, "first_name", "") or "", getattr(t, "middle_name", "") or ""]
                ).strip(),
            })

    # subjects
    s_name = _first_attr(Subject, ["name", "title"])
    if s_name is not None:
        rs = (
            db.session.query(Subject)
            .filter(func.lower(s_name).like(f"%{q}%"))
            .order_by(s_name.asc())
            .limit(limit)
            .all()
        )
        for s in rs:
            items.append({
                "type": "subject",
                "id": getattr(s, "id", None),
                "label": getattr(s, "name", None) or getattr(s, "title", None),
            })

    return jsonify({"items": items[:limit]})


# ----- SCHEDULE -----
@bp.get("/schedule/group/<code>")
def schedule_group(code):
    """Вернёт расписание для группы (day/week). Всегда один и тот же формат JSON."""
    rng = (request.args.get("range") or "day").lower()
    # дата из параметров
    try:
        target_date = datetime.fromisoformat(request.args.get("date")).date()
    except Exception:
        target_date = datetime.now().date()

    # ищем группу (по code/name/label)
    g_code = _first_attr(Group, ["code", "label", "name"])
    group = (
        db.session.query(Group)
        .filter(func.lower(g_code) == code.lower())
        .first()
        if g_code is not None else None
    )
    if not group:
        return jsonify({"lessons": []}) if rng == "day" else jsonify({"days": []})

    # поле даты
    l_date = _date_col()

    # базовый запрос
    q = db.session.query(Lesson)

    # присоединим слот (мягко)
    slot_joined = False
    if TimeSlot is not None and hasattr(Lesson, "time_slot_id") and hasattr(TimeSlot, "id"):
        q = q.join(TimeSlot, Lesson.time_slot_id == TimeSlot.id, isouter=True)
        slot_joined = True

    # фильтры по группе
    if hasattr(Lesson, "group_id") and hasattr(group, "id"):
        q = q.filter(Lesson.group_id == group.id)

    # сортировка
    order_col = _order_col()
    if slot_joined and order_col is not None and order_col.class_ is TimeSlot:
        q = q.order_by(order_col.asc())
    elif hasattr(Lesson, "order_no") or hasattr(Lesson, "order"):
        q = q.order_by((_first_attr(Lesson, ["order_no", "order"])).asc())

    def _normalize_row(row):
        slot = None
        if slot_joined:
            # когда join'им, SQLAlchemy кладёт вторую сущность в row[1] только если select_entities;
            # поэтому лучше вытягивать из связанного атрибута
            slot = getattr(row, "time_slot", None)
        return _normalize_lesson(row, slot)

    if rng == "day":
        qd = q.filter(l_date == target_date).all()
        out = [_normalize_row(r) for r in qd]
        out = _insert_breaks(out)
        return jsonify({"lessons": out})

    # rng == "week"
    # определим понедельник той недели
    weekday = target_date.weekday()  # 0..6
    week_start = target_date - timedelta(days=weekday)
    days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        qd = q.filter(l_date == d).all()
        items = [_normalize_row(r) for r in qd]
        items = _insert_breaks(items)
        days.append({
            "date": d.isoformat(),
            "lessons": items
        })

    return jsonify({"days": days})
