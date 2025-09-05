from datetime import date, datetime, timedelta
import importlib
from flask import request, jsonify
from sqlalchemy import func, or_
from extensions import db
from . import bp

# ---------- УНИВЕРСАЛЬНЫЕ ИМПОРТЫ МОДЕЛЕЙ С ФОЛЛБЭКАМИ ----------
def _import_any(candidates):
    last_err = None
    for module_path, name in candidates:
        try:
            mod = importlib.import_module(module_path)
            return getattr(mod, name)
        except Exception as e:
            last_err = e
    if last_err:
        # Вернём None — код ниже умеет работать с отсутствием отдельных моделей
        return None
    return None

Group    = _import_any([("models.group", "Group"), ("models.groups", "Group")])
Teacher  = _import_any([("models.teacher", "Teacher"), ("models.teachers", "Teacher")])
Subject  = _import_any([("models.subject", "Subject"), ("models.subjects", "Subject")])
Room     = _import_any([("models.room", "Room"), ("models.rooms", "Room")])
Lesson   = _import_any([("models.lesson", "Lesson"), ("models.lessons", "Lesson")])
TimeSlot = _import_any([("models.timeslot", "TimeSlot"), ("models.time_slot", "TimeSlot"), ("models.slot", "TimeSlot")])
LessonType = _import_any([("models.lesson_type", "LessonType"), ("models.lessontype", "LessonType")])
Homework = _import_any([("models.homework", "Homework")])

# ---------- ВСПОМОГАТЕЛЬНОЕ ----------
def _col(model, names):
    """Вернуть первый существующий атрибут модели из списка имён (или None)."""
    if not model:
        return None
    for n in names:
        if hasattr(model, n):
            return getattr(model, n)
    return None

def _to_hhmm(value):
    """time|str|None -> 'HH:MM' или ''"""
    if value is None:
        return ""
    if isinstance(value, str):
        # допускаем '8:30'/'08:30'
        try:
            parts = value.split(":")
            h = int(parts[0]); m = int(parts[1])
            return f"{h:02d}:{m:02d}"
        except Exception:
            return value
    try:
        return f"{value.hour:02d}:{value.minute:02d}"
    except Exception:
        return str(value)

def _lesson_date_col():
    """Определяем, по какому полю хранится дата занятия."""
    return _col(Lesson, ["date", "lesson_date", "day"])

def _lesson_order_col():
    """Определяем поле с порядковым номером пары (если нет TimeSlot)."""
    return _col(Lesson, ["order_no", "order"])

def _slot_order_col():
    return _col(TimeSlot, ["order_no", "order"])

def _slot_start_col():
    return _col(TimeSlot, ["start_time", "start"])

def _slot_end_col():
    return _col(TimeSlot, ["end_time", "end"])

def _group_code_col():
    return _col(Group, ["code"])

def _group_name_col():
    return _col(Group, ["name", "title", "label"])

def _teacher_name_display(t):
    # предпочитаем full_name; иначе склеим ФИО из имеющихся частей
    val = getattr(t, "full_name", None)
    if val:
        return val
    ln = getattr(t, "last_name", "") or ""
    fn = getattr(t, "first_name", "") or ""
    mn = getattr(t, "middle_name", "") or ""
    return " ".join(x for x in [ln, fn, mn] if x).strip()

def _subject_name_display(s):
    return getattr(s, "name", None) or getattr(s, "title", None) or ""

def _room_number_display(r):
    return getattr(r, "number", None) or getattr(r, "name", None) or ""

def _lesson_type_name_display(lt):
    return getattr(lt, "name", None) or getattr(lt, "title", None) or "Занятие"

def _bool_attr(obj, names, default=False):
    for n in names:
        if hasattr(obj, n):
            return bool(getattr(obj, n))
    return default

def _serialize_lesson(l):
    """Собираем единый формат занятия для фронта."""
    # связь со слотами (если есть FK)
    ts = getattr(l, "time_slot", None)

    # времена и номер
    if ts is not None:
        s = _to_hhmm(getattr(ts, _slot_start_col().__name__, None) if _slot_start_col() else getattr(ts, "start_time", None))
        e = _to_hhmm(getattr(ts, _slot_end_col().__name__, None) if _slot_end_col() else getattr(ts, "end_time", None))
        ord_val = getattr(ts, _slot_order_col().__name__, None) if _slot_order_col() else getattr(ts, "order_no", None)
    else:
        # нет связи со слотами — попробуем взять из полей самой пары
        s = _to_hhmm(getattr(l, "start_time", None))
        e = _to_hhmm(getattr(l, "end_time", None))
        ord_val = getattr(l, _lesson_order_col().__name__, None) if _lesson_order_col() else getattr(l, "order_no", None)

    subj = getattr(l, "subject", None)
    tchr = getattr(l, "teacher", None)
    room = getattr(l, "room", None)
    ltype = getattr(l, "lesson_type", None)
    hw = None
    if Homework and hasattr(l, "homeworks"):
        try:
            hw_obj = next(iter(getattr(l, "homeworks")), None)
            if hw_obj:
                hw = {"text": getattr(hw_obj, "text", "")}
        except Exception:
            pass

    return {
        "time_slot": {
            "order_no": ord_val or 0,
            "start_time": s or "",
            "end_time": e or "",
        },
        "subject": {"name": _subject_name_display(subj)} if subj else {"name": ""},
        "teacher": {"full_name": _teacher_name_display(tchr)} if tchr else {"full_name": ""},
        "room": {"number": _room_number_display(room)} if room else None,
        "lesson_type": {"name": _lesson_type_name_display(ltype)} if ltype else {"name": "Занятие"},
        "is_remote": _bool_attr(l, ["is_remote", "remote", "online"], False),
        "homework": hw
    }

def _insert_breaks(sorted_lessons):
    """Вставляем «перерывы» между слотами, если есть разрывы во времени."""
    out = []
    prev_end = None
    for item in sorted_lessons:
        start = item["time_slot"]["start_time"]
        if prev_end and start and prev_end < start:
            out.append({"is_break": True, "from": prev_end, "to": start})
        out.append(item)
        prev_end = item["time_slot"]["end_time"]
    return out

def _parse_iso(dstr):
    try:
        return datetime.strptime(dstr, "%Y-%m-%d").date()
    except Exception:
        return date.today()

# ---------- /suggest ----------
@bp.get("/suggest")
def suggest():
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 10)
    items = []

    if not q:
        return jsonify({"items": []})

    q_low = q.lower()

    # groups
    if Group:
        code_c = _group_code_col()
        name_c = _group_name_col()
        conds = []
        if code_c is not None:
            conds.append(func.lower(code_c).like(f"%{q_low}%"))
        if name_c is not None:
            conds.append(func.lower(name_c).like(f"%{q_low}%"))
        if conds:
            rows = (
                db.session.query(Group)
                .filter(or_(*conds))
                .order_by(code_c.asc() if code_c is not None else name_c.asc())
                .limit(limit)
                .all()
            )
            for g in rows:
                code_val = getattr(g, code_c.key if code_c is not None else "code", None)
                label_val = getattr(g, name_c.key if name_c is not None else "name", None)
                items.append({
                    "type": "group",
                    "id": getattr(g, "id", None),
                    "code": code_val,
                    "label": code_val or label_val or f"Группа #{getattr(g, 'id', '')}"
                })

    # teachers
    if Teacher:
        full = _col(Teacher, ["full_name"])
        ln = _col(Teacher, ["last_name"])
        fn = _col(Teacher, ["first_name"])
        mn = _col(Teacher, ["middle_name"])

        conds = []
        if full is not None:
            conds.append(func.lower(full).like(f"%{q_low}%"))
        if ln is not None:
            conds.append(func.lower(ln).like(f"%{q_low}%"))
        if fn is not None:
            conds.append(func.lower(fn).like(f"%{q_low}%"))
        if mn is not None:
            conds.append(func.lower(mn).like(f"%{q_low}%"))
        if conds:
            rows = (
                db.session.query(Teacher)
                .filter(or_(*conds))
                .order_by((full or ln).asc())
                .limit(limit)
                .all()
            )
            for t in rows:
                items.append({
                    "type": "teacher",
                    "id": getattr(t, "id", None),
                    "label": _teacher_name_display(t)
                })

    # subjects
    if Subject:
        nm = _col(Subject, ["name", "title"])
        if nm is not None:
            rows = (
                db.session.query(Subject)
                .filter(func.lower(nm).like(f"%{q_low}%"))
                .order_by(nm.asc())
                .limit(limit)
                .all()
            )
            for s in rows:
                items.append({
                    "type": "subject",
                    "id": getattr(s, "id", None),
                    "label": _subject_name_display(s)
                })

    return jsonify({"items": items})

# ---------- /schedule/group/<code> ----------
@bp.get("/schedule/group/<code>")
def schedule_group(code):
    """Вернуть расписание группы на день или неделю.
    ?date=YYYY-MM-DD&range=day|week
    """
    if not Group or not Lesson:
        return jsonify({"lessons": []})  # минимальная защита

    date_str = request.args.get("date") or date.today().isoformat()
    range_mode = (request.args.get("range") or "day").lower()
    target = _parse_iso(date_str)

    # Найти группу по коду (или по имени, если поле code отсутствует)
    code_c = _group_code_col()
    name_c = _group_name_col()
    q = db.session.query(Group)
    if code_c is not None:
        grp = q.filter(func.lower(code_c) == code.lower()).first()
    else:
        grp = q.filter(func.lower(name_c) == code.lower()).first() if name_c is not None else None

    if not grp:
        return jsonify({"lessons": []})

    if range_mode == "week":
        # Понедельник той недели
        start = target - timedelta(days=(target.weekday() % 7))
        days = []
        for i in range(7):
            d = start + timedelta(days=i)
            lessons = _load_day_lessons(grp, d)
            days.append({"date": d.isoformat(), "lessons": lessons})
        return jsonify({"days": days})

    # по умолчанию: день
    lessons = _load_day_lessons(grp, target)
    return jsonify({"lessons": lessons})

def _load_day_lessons(group_obj, day_dt):
    """Загрузить пары на конкретный день и вернуть сериализованный список с перерывами."""
    day_col = _lesson_date_col()
    if day_col is None:
        # если в модели урока нет поля даты — нечего отдавать
        return []

    # Базовый запрос по группе и дате
    q = db.session.query(Lesson).filter(
        day_col == day_dt
    )

    # фильтр по группе — пробуем разные варианты
    if hasattr(Lesson, "group_id") and hasattr(group_obj, "id"):
        q = q.filter(getattr(Lesson, "group_id") == getattr(group_obj, "id"))
    elif hasattr(Lesson, "group") and hasattr(group_obj, "id"):
        # ORM-связь
        q = q.filter(getattr(Lesson, "group") == group_obj)

    # Сортировка по слоту/порядку
    if hasattr(Lesson, "time_slot") and TimeSlot and _slot_order_col() is not None:
        # если настроена связь с TimeSlot, отсортируем по order_no слота
        # сделаем простой Python-сорт после выборки, чтобы не лепить join при любых схемах
        rows = q.all()
        rows.sort(key=lambda l: getattr(getattr(l, "time_slot"), _slot_order_col().__name__, getattr(getattr(l, "time_slot"), "order_no", 0)) if getattr(l, "time_slot", None) else getattr(l, _lesson_order_col().__name__, getattr(l, "order_no", 0)))
    else:
        rows = q.order_by((_lesson_order_col() or _col(Lesson, ["start_time"])).asc()).all()

    serialized = [_serialize_lesson(l) for l in rows]
    # Вставим «перерывы» между занятиями
    serialized.sort(key=lambda x: (x["time_slot"]["order_no"] or 0, x["time_slot"]["start_time"]))
    serialized = _insert_breaks(serialized)
    return serialized
