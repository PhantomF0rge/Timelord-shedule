from datetime import date, timedelta
from flask import request, jsonify
from sqlalchemy import or_, func
from . import bp

# Мягкие импорты: берём то, что есть, без падений
def _try_import(module_path, name):
    try:
        mod = __import__(module_path, fromlist=[name])
        return getattr(mod, name, None)
    except Exception:
        return None

# БД-сессия
_extensions_db = _try_import("extensions", "db")
db = _extensions_db

# Модели (любая может отсутствовать — код переживёт)
Group    = _try_import("models.group",    "Group")
Teacher  = _try_import("models.teacher",  "Teacher")
Subject  = _try_import("models.subject",  "Subject")
TimeSlot = _try_import("models.timeslot", "TimeSlot")
Lesson   = _try_import("models.lesson",   "Lesson")
Room     = _try_import("models.room",     "Room")
LType    = _try_import("models.lesson_type", "LessonType")
Homework = _try_import("models.homework", "Homework")

# ---- УТИЛИТЫ -----------------------------------------------------------------

def _lesson_date_col():
    """Возвращает колонку даты у Lesson, как она называется в твоих моделях."""
    if Lesson is None:
        return None
    for cand in ("date", "lesson_date", "day"):
        if hasattr(Lesson, cand):
            return getattr(Lesson, cand)
    return None

def _slot_order_col():
    """Возвращает колонку порядка у TimeSlot: order_no или order."""
    if TimeSlot is None:
        return None
    for cand in ("order_no", "order"):
        if hasattr(TimeSlot, cand):
            return getattr(TimeSlot, cand)
    return None

def _time_cols(model):
    """Вернёт (start_time, end_time) если есть у модели."""
    st = getattr(model, "start_time", None) if model else None
    et = getattr(model, "end_time", None) if model else None
    return st, et

def _safe_val(obj, *names, default=None):
    """Вернёт первое существующее свойство из names у объекта."""
    for n in names:
        if obj is not None and hasattr(obj, n):
            return getattr(obj, n)
    return default

def _get_by_id(Model, id_):
    if Model is None or id_ is None or db is None:
        return None
    try:
        return db.session.get(Model, id_)
    except Exception:
        return None

def _subject_of(lesson):
    # либо отношение, либо по FK
    s = _safe_val(lesson, "subject", default=None)
    if s is None:
        s_id = _safe_val(lesson, "subject_id", default=None)
        s = _get_by_id(Subject, s_id)
    return s

def _teacher_of(lesson):
    t = _safe_val(lesson, "teacher", default=None)
    if t is None:
        t_id = _safe_val(lesson, "teacher_id", default=None)
        t = _get_by_id(Teacher, t_id)
    return t

def _room_of(lesson):
    r = _safe_val(lesson, "room", default=None)
    if r is None:
        r_id = _safe_val(lesson, "room_id", default=None)
        r = _get_by_id(Room, r_id)
    return r

def _ltype_of(lesson):
    lt = _safe_val(lesson, "lesson_type", default=None)
    if lt is None:
        lt_id = _safe_val(lesson, "lesson_type_id", default=None)
        lt = _get_by_id(LType, lt_id)
    return lt

def _homework_of(lesson):
    # либо отношение Homeworks, либо отдельная модель с FK lesson_id
    hw = _safe_val(lesson, "homework", default=None)
    if hw:
        return hw
    if Homework is None or db is None:
        return None
    try:
        return db.session.query(Homework).filter(
            _safe_val(Homework, "lesson_id") == _safe_val(lesson, "id")
        ).first()
    except Exception:
        return None

def _lesson_to_json(lesson, slot_cache=None):
    """Собираем JSON пары. Работает даже с урезанными моделями."""
    # время и номер пары — пытаемся брать из TimeSlot, если задан
    slot = None
    ts_id = _safe_val(lesson, "time_slot_id", default=None)
    if ts_id and slot_cache is not None:
        slot = slot_cache.get(ts_id)

    # если слота нет — берём из полей самой пары, если такие есть
    l_start = _safe_val(lesson, "start_time", default=None)
    l_end   = _safe_val(lesson, "end_time", default=None)
    l_ord   = _safe_val(lesson, "order_no", "order", default=None)

    if slot is not None:
        s_start = _safe_val(slot, "start_time")
        s_end   = _safe_val(slot, "end_time")
        s_ord   = _safe_val(slot, "order_no", "order")
        start_time = (s_start or l_start)
        end_time   = (s_end   or l_end)
        order_no   = (s_ord   or l_ord)
    else:
        start_time = l_start
        end_time   = l_end
        order_no   = l_ord

    subj = _subject_of(lesson)
    teach = _teacher_of(lesson)
    room = _room_of(lesson)
    ltype = _ltype_of(lesson)
    hw = _homework_of(lesson)

    is_remote = bool(_safe_val(lesson, "is_remote", "remote", "online", default=False))

    def _time_to_str(t):
        try:
            return t.strftime("%H:%M")
        except Exception:
            return None

    return {
        "id": _safe_val(lesson, "id"),
        "subject": {
            "id": _safe_val(subj, "id"),
            "name": _safe_val(subj, "name", "title", default=""),
        },
        "teacher": {
            "id": _safe_val(teach, "id"),
            "full_name": _safe_val(teach, "full_name",
                                   default=(" ".join(filter(None, [
                                       _safe_val(teach, "last_name", default=""),
                                       _safe_val(teach, "first_name", default=""),
                                       _safe_val(teach, "middle_name", default="")
                                   ])).strip())),
        },
        "room": (None if is_remote else {
            "id": _safe_val(room, "id"),
            "number": _safe_val(room, "number", default=""),
        }),
        "lesson_type": ({
            "id": _safe_val(ltype, "id"),
            "name": _safe_val(ltype, "name", "title", default="")
        } if ltype else None),
        "time_slot": {
            "id": ts_id,
            "order_no": order_no,
            "start_time": _time_to_str(start_time),
            "end_time": _time_to_str(end_time),
        },
        "is_remote": is_remote,
        "homework": ({"text": _safe_val(hw, "text", default="")} if hw else None),
    }

def _insert_breaks(day_lessons, all_slots):
    """Вставляет 'перерывы' в отсутствующие слоты между первой и последней занятой парой."""
    if not day_lessons or not all_slots:
        return day_lessons

    order_attr = "order_no" if hasattr(TimeSlot, "order_no") else "order"
    slots_sorted = sorted(all_slots, key=lambda s: getattr(s, order_attr))
    used_orders = set()
    for l in day_lessons:
        ts = l.get("time_slot") or {}
        ord_no = ts.get("order_no")
        if ord_no is not None:
            used_orders.add(ord_no)

    if not used_orders:
        return day_lessons

    min_ord = min(used_orders)
    max_ord = max(used_orders)

    slot_map = {getattr(s, order_attr): s for s in slots_sorted}

    # Собираем финальный список с перерывами
    out = []
    # Для равномерной сортировки по порядку
    all_by_order = { l["time_slot"]["order_no"]: l for l in day_lessons if l.get("time_slot") }

    for ord_no in range(min_ord, max_ord + 1):
        if ord_no in used_orders:
            out.append(all_by_order[ord_no])
        else:
            s = slot_map.get(ord_no)
            if not s:
                continue
            st, et = _time_cols(s)
            out.append({
                "is_break": True,
                "from": st.strftime("%H:%M") if st else None,
                "to": et.strftime("%H:%M") if et else None
            })

    # Сортируем на всякий
    out.sort(key=lambda x: (0 if not x.get("is_break") else 1,
                            x.get("time_slot", {}).get("order_no", 999)))
    return out

# ---- /suggest ---------------------------------------------------------------

@bp.get("/suggest")
def suggest():
    """
    GET /api/v1/suggest?q=...&limit=10
    Возвращает items: [{type, id, label, code?}]
    type: group|teacher|subject
    """
    if db is None:
        return jsonify({"items": []})

    q = (request.args.get("q") or "").strip().lower()
    limit = int(request.args.get("limit", 10))

    items = []

    # Groups
    if Group is not None and q:
        try:
            crit = or_(func.lower(Group.code).like(f"%{q}%"),
                       func.lower(Group.name).like(f"%{q}%"))
            groups = (
                db.session.query(Group)
                .filter(crit)
                .order_by(Group.code.asc())
                .limit(limit)
                .all()
            )
            for g in groups:
                items.append({
                    "type": "group",
                    "id": _safe_val(g, "id"),
                    "label": f"{_safe_val(g,'code','')}{' · ' + _safe_val(g,'name','') if _safe_val(g,'name') else ''}",
                    "code": _safe_val(g, "code")
                })
        except Exception:
            pass

    # Teachers
    if Teacher is not None and q:
        try:
            parts = [func.lower(Teacher.full_name).like(f"%{q}%")]
            # Если ФИО разбито — ищем и по ним
            for attr in ("last_name", "first_name", "middle_name"):
                if hasattr(Teacher, attr):
                    parts.append(func.lower(getattr(Teacher, attr)).like(f"%{q}%"))
            crit = or_(*parts)
            teachers = (
                db.session.query(Teacher)
                .filter(crit)
                .order_by(Teacher.id.asc())
                .limit(limit)
                .all()
            )
            for t in teachers:
                items.append({
                    "type": "teacher",
                    "id": _safe_val(t, "id"),
                    "label": _safe_val(t, "full_name",
                                       default=(" ".join(filter(None, [
                                           _safe_val(t, "last_name", default=""),
                                           _safe_val(t, "first_name", default=""),
                                           _safe_val(t, "middle_name", default="")
                                       ])).strip()))
                })
        except Exception:
            pass

    # Subjects
    if Subject is not None and q:
        try:
            parts = []
            for attr in ("name", "title"):
                if hasattr(Subject, attr):
                    parts.append(func.lower(getattr(Subject, attr)).like(f"%{q}%"))
            if parts:
                crit = or_(*parts)
                subjects = (
                    db.session.query(Subject)
                    .filter(crit)
                    .order_by(_safe_val(Subject, "name", "title"))
                    .limit(limit)
                    .all()
                )
                for s in subjects:
                    items.append({
                        "type": "subject",
                        "id": _safe_val(s, "id"),
                        "label": _safe_val(s, "name", "title", default="")
                    })
        except Exception:
            pass

    return jsonify({"items": items})

# ---- /schedule/group/<code>  -----------------------------------------------

@bp.get("/schedule/group/<code>")
def schedule_group(code):
    """
    GET /api/v1/schedule/group/<code>?date=YYYY-MM-DD&range=day|week
    Возвращает:
      - range=day: {date, lessons:[...] }
      - range=week: {week_start, week_end, days:[{date, lessons:[...]}] }
    """
    if db is None or Lesson is None or Group is None:
        return jsonify({"error": "models unavailable", "lessons": []}), 200

    # Параметры
    try:
        day_str = request.args.get("date")
        base_day = date.fromisoformat(day_str) if day_str else date.today()
    except Exception:
        base_day = date.today()
    rng = request.args.get("range", "day").lower()
    if rng not in ("day", "week"):
        rng = "day"

    # Ищем группу
    g = db.session.query(Group).filter(Group.code == code).first()
    if not g:
        return jsonify({"date": base_day.isoformat(), "lessons": []}), 200

    # Загружаем все слоты (для «перерывов») и подготовим кэш
    slot_order_col = _slot_order_col()
    slot_start, slot_end = _time_cols(TimeSlot)
    all_slots = []
    slot_cache = {}
    if TimeSlot is not None and slot_order_col is not None:
        try:
            all_slots = (
                db.session.query(TimeSlot)
                .order_by(slot_order_col.asc())
                .all()
            )
            for s in all_slots:
                slot_cache[_safe_val(s, "id")] = s
        except Exception:
            all_slots = []

    date_col = _lesson_date_col()

    def _fetch_for_day(d: date):
        q = db.session.query(Lesson).filter(_safe_val(Lesson, "group_id") == _safe_val(g, "id"))

        if date_col is not None:
            q = q.filter(date_col == d)

        # сортировка: по order_no/ order (если есть), иначе по time_slot -> по слоту
        order_attr = "order_no" if hasattr(Lesson, "order_no") else ("order" if hasattr(Lesson, "order") else None)
        if order_attr is not None:
            q = q.order_by(getattr(Lesson, order_attr).asc())
        elif hasattr(Lesson, "time_slot_id") and slot_order_col is not None:
            # сортируем через join слотов
            try:
                q = q.join(TimeSlot, _safe_val(Lesson, "time_slot_id") == _safe_val(TimeSlot, "id")) \
                     .order_by(slot_order_col.asc())
            except Exception:
                pass

        rows = q.all()
        items = [_lesson_to_json(l, slot_cache=slot_cache) for l in rows]
        items = _insert_breaks(items, all_slots)
        return {"date": d.isoformat(), "lessons": items}

    if rng == "day":
        return jsonify(_fetch_for_day(base_day)), 200

    # week
    # Неделя: понедельник..воскресенье с базовым днём внутри
    week_start = base_day - timedelta(days=base_day.weekday())  # Пн
    days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        days.append(_fetch_for_day(d))
    return jsonify({
        "week_start": week_start.isoformat(),
        "week_end": (week_start + timedelta(days=6)).isoformat(),
        "days": days
    }), 200
