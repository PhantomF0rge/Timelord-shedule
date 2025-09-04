from datetime import datetime, date as ddate, time as dtime
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_
from extensions import db
from . import bp

# Аккуратно тянем модели
def _safe_import(path, name):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name, None)
    except Exception:
        return None

Group      = _safe_import("models.group", "Group")
Teacher    = _safe_import("models.teacher", "Teacher")
Subject    = _safe_import("models.subject", "Subject")
Room       = _safe_import("models.room", "Room")
Lesson     = _safe_import("models.lesson", "Lesson")
TimeSlot   = _safe_import("models.timeslot", "TimeSlot")
LessonType = _safe_import("models.lesson_type", "LessonType")

def has_attr(obj_or_cls, name: str) -> bool:
    try:
        return hasattr(obj_or_cls, name)
    except Exception:
        return False

def col(model, *candidates):
    for name in candidates:
        if has_attr(model, name):
            return getattr(model, name)
    return None

# Универсальные ссылки на поля Lesson/TimeSlot
L_DATE   = col(Lesson, "date", "lesson_date", "day")
L_SLOTID = col(Lesson, "time_slot_id")
L_START  = col(Lesson, "start_time")
L_END    = col(Lesson, "end_time")
L_GROUP  = col(Lesson, "group_id")
L_TEACH  = col(Lesson, "teacher_id")
L_ROOM   = col(Lesson, "room_id")
L_ORDER  = col(Lesson, "order_no", "order")

TS_ORDER = col(TimeSlot, "order_no", "order")
TS_START = col(TimeSlot, "start_time")
TS_END   = col(TimeSlot, "end_time")

def _overlap_q(date, slot_id=None, start=None, end=None):
    if L_SLOTID is not None and slot_id is not None:
        return and_(L_DATE == date, L_SLOTID == slot_id)
    if L_START is not None and L_END is not None and start is not None and end is not None:
        return and_(L_DATE == date, L_START < end, start < L_END)
    if L_ORDER is not None and start is not None:
        return and_(L_DATE == date, L_ORDER == start)
    return and_(L_DATE == date, False)

def _parse_date(s):
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return ddate.today()

def _int_or_none(x):
    try:
        v = int(x)
        return v if v >= 0 else None
    except Exception:
        return None

def _all(model, order_col=None):
    if model is None:
        return []
    q = db.session.query(model)
    if order_col is not None:
        q = q.order_by(order_col.asc())
    return q.all()

# --- ЕДИНАЯ проверка прав администратора (совместима с разными моделями User)
def _is_admin_user():
    # 1) Явный метод
    if hasattr(current_user, "is_admin"):
        try:
            if current_user.is_admin():
                return True
        except Exception:
            pass
    # 2) Поле role
    role = getattr(current_user, "role", None)
    if isinstance(role, str) and role.lower() in ("admin", "administrator", "superadmin"):
        return True
    return False

# --- Страница планировщика
@bp.get("/builder")
@login_required
def builder_index():
    if not _is_admin_user():
        flash("Требуются права администратора", "error")
        return redirect(url_for("core.index"))

    groups        = _all(Group,   order_col=col(Group, "code"))
    teachers      = _all(Teacher, order_col=col(Teacher, "last_name", "full_name"))
    subjects      = _all(Subject, order_col=col(Subject, "name", "title"))
    rooms         = _all(Room,    order_col=col(Room, "number"))
    slots         = _all(TimeSlot, order_col=TS_ORDER) if TimeSlot else []
    lesson_types  = _all(LessonType, order_col=col(LessonType, "name", "title")) if LessonType else []

    today_str = ddate.today().isoformat()

    return render_template("planning/builder.html",
                           groups=groups, teachers=teachers, subjects=subjects,
                           rooms=rooms, slots=slots, lesson_types=lesson_types,
                           today_str=today_str)

# --- Проверка конфликтов/подбор аудитории
@bp.post("/builder/check")
@login_required
def builder_check():
    if not _is_admin_user():
        return jsonify({"ok": False, "errors": [{"code": "forbidden", "message": "Нет прав"}]}), 403

    data = request.get_json(silent=True) or request.form
    day = _parse_date(data.get("date") or ddate.today().isoformat())
    group_id   = _int_or_none(data.get("group_id"))
    teacher_id = _int_or_none(data.get("teacher_id"))
    room_id    = _int_or_none(data.get("room_id"))
    slot_id    = _int_or_none(data.get("time_slot_id"))
    order_no   = _int_or_none(data.get("order_no"))
    require_pc = str(data.get("require_pc", "0")) in ("1", "true", "True")

    start = end = None
    if data.get("start_time") and data.get("end_time"):
        try:
            h, m = map(int, data.get("start_time").split(":"))
            start = dtime(h, m)
            h2, m2 = map(int, data.get("end_time").split(":"))
            end = dtime(h2, m2)
        except Exception:
            start = end = None

    required_capacity = None
    if Group is not None and group_id:
        g = db.session.get(Group, group_id)
        if g and hasattr(g, "students_count"):
            required_capacity = getattr(g, "students_count")

    errors = []
    suggestions = {"rooms": []}

    # вместимость/ПК по выбранной аудитории
    if room_id and Room is not None:
        r = db.session.get(Room, room_id)
        g = db.session.get(Group, group_id) if Group and group_id else None
        if r and g and hasattr(g, "students_count"):
            size = getattr(g, "students_count") or 0
            if hasattr(r, "capacity"):
                cap = getattr(r, "capacity") or 0
                if cap and size and size > cap:
                    errors.append({"code": "room_capacity", "message": f"В группе {size} чел., аудитория вмещает {cap}."})
            if require_pc:
                pc = None
                for fld in ("computers_count", "computers"):
                    if hasattr(r, fld):
                        pc = getattr(r, fld) or 0
                        break
                if pc is not None and size > pc:
                    errors.append({"code": "room_computers", "message": f"Компьютеров {pc}, студентов {size}."})

    time_filter = _overlap_q(day, slot_id=slot_id, start=start or order_no, end=end)

    if Lesson is not None:
        if room_id and L_ROOM is not None:
            if db.session.query(Lesson).filter(and_(time_filter, L_ROOM == room_id)).first():
                errors.append({"code": "room_busy", "message": "Аудитория занята в это время."})
        if group_id and L_GROUP is not None:
            if db.session.query(Lesson).filter(and_(time_filter, L_GROUP == group_id)).first():
                errors.append({"code": "group_busy", "message": "У группы в это время уже есть занятие."})
        if teacher_id and L_TEACH is not None:
            if db.session.query(Lesson).filter(and_(time_filter, L_TEACH == teacher_id)).first():
                errors.append({"code": "teacher_busy", "message": "У преподавателя в это время уже есть занятие."})

        # предложения свободных аудиторий
        if Room is not None:
            free = []
            for r in db.session.query(Room).all():
                if required_capacity and hasattr(r, "capacity"):
                    cap = getattr(r, "capacity") or 0
                    if cap and cap < required_capacity:
                        continue
                if require_pc:
                    pc = None
                    for fld in ("computers_count", "computers"):
                        if hasattr(r, fld):
                            pc = getattr(r, fld) or 0
                            break
                    if pc is not None and required_capacity and pc < required_capacity:
                        continue
                if L_ROOM is not None:
                    if db.session.query(Lesson).filter(and_(time_filter, L_ROOM == getattr(r, "id"))).first():
                        continue
                free.append({"id": getattr(r, "id"), "label": getattr(r, "number", f"#{getattr(r, 'id')}")})
            suggestions["rooms"] = free[:10]

    return jsonify({"ok": len(errors) == 0, "errors": errors, "warnings": [], "suggestions": suggestions})

# --- Создание пары
@bp.post("/builder/create")
@login_required
def builder_create():
    if not _is_admin_user():
        flash("Нет прав", "error")
        return redirect(url_for("planning.builder_index"))

    f = request.form
    day        = _parse_date(f.get("date") or ddate.today().isoformat())
    group_id   = _int_or_none(f.get("group_id"))
    teacher_id = _int_or_none(f.get("teacher_id"))
    subject_id = _int_or_none(f.get("subject_id"))
    room_id    = _int_or_none(f.get("room_id"))
    slot_id    = _int_or_none(f.get("time_slot_id"))
    order_no   = _int_or_none(f.get("order_no"))
    ltype_id   = _int_or_none(f.get("lesson_type_id"))
    is_remote  = str(f.get("is_remote", "0")) in ("1", "true", "True")

    start = end = None
    if f.get("start_time") and f.get("end_time"):
        try:
            h, m = map(int, f.get("start_time").split(":"))
            start = dtime(h, m)
            h2, m2 = map(int, f.get("end_time").split(":"))
            end = dtime(h2, m2)
        except Exception:
            start = end = None

    # повторная валидация через тот же код
    check_resp = builder_check()
    res_json = check_resp[0].json if isinstance(check_resp, tuple) else check_resp.json
    if not res_json.get("ok"):
        for e in res_json.get("errors", []):
            flash(f"Ошибка: {e['message']}", "error")
        return redirect(url_for("planning.builder_index"))

    if Lesson is None:
        flash("Модель Lesson отсутствует", "error")
        return redirect(url_for("planning.builder_index"))

    lesson = Lesson()
    if L_DATE is not None:          setattr(lesson, L_DATE.key, day)
    if L_SLOTID is not None and slot_id is not None: setattr(lesson, L_SLOTID.key, slot_id)
    if L_START is not None and start is not None:    setattr(lesson, L_START.key, start)
    if L_END is not None and end is not None:        setattr(lesson, L_END.key, end)
    if L_ORDER is not None and order_no is not None: setattr(lesson, L_ORDER.key, order_no)

    if L_GROUP is not None and group_id:   setattr(lesson, L_GROUP.key, group_id)
    if L_TEACH is not None and teacher_id: setattr(lesson, L_TEACH.key, teacher_id)
    if L_ROOM is not None:                 setattr(lesson, L_ROOM.key, room_id)
    if has_attr(lesson, "subject_id") and subject_id:       setattr(lesson, "subject_id", subject_id)
    if has_attr(lesson, "lesson_type_id") and ltype_id:     setattr(lesson, "lesson_type_id", ltype_id)

    for flag in ("is_remote", "remote", "online"):
        if has_attr(lesson, flag):
            setattr(lesson, flag, bool(is_remote))
            break

    db.session.add(lesson)
    db.session.commit()
    flash("Пара добавлена", "success")
    return redirect(url_for("planning.builder_index"))
