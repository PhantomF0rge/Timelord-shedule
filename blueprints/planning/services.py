from datetime import timedelta
from sqlalchemy import and_, or_
from extensions import db

# Аккуратно тянем модели: под разные имена полей.
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
    """Вернёт первый существующий столбец модели из списка candidates."""
    for name in candidates:
        if has_attr(model, name):
            return getattr(model, name)
    return None

# Универсальные "колонки" для разных схем
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

R_CAP    = col(Room, "capacity")
R_PC     = col(Room, "computers_count", "computers")

def _overlap_q(date, slot_id=None, start=None, end=None):
    """SQLAlchemy фильтр пересечения занятия с указанным временем."""
    if L_SLOTID is not None and slot_id is not None:
        return and_(L_DATE == date, L_SLOTID == slot_id)
    # Режим по времени, если слотов нет
    if L_START is not None and L_END is not None and start is not None and end is not None:
        # Пересечение интервалов: (A.start < B.end) и (B.start < A.end)
        return and_(L_DATE == date, L_START < end, start < L_END)
    # fallback по порядковому номеру пары
    if L_ORDER is not None:
        return and_(L_DATE == date, L_ORDER == start)  # тут start = order_no
    # если вообще нечем сравнивать — вернём False
    return and_(L_DATE == date, False)

def check_conflicts(date, group_id, teacher_id, room_id,
                    slot_id=None, order_no=None, start=None, end=None,
                    require_computers=False, required_capacity=None):
    """
    Возвращает (errors, warnings, suggestions)
    errors: список dict {code, message}
    suggestions: {'rooms': [ {id, label} , ... ]}
    """
    errors = []
    warnings = []
    suggestions = {"rooms": []}

    # --- загрузка выбранной аудитории/группы/преподавателя
    room = db.session.get(Room, room_id) if Room and room_id else None
    group = db.session.get(Group, group_id) if Group and group_id else None

    # --- проверка вместимости
    if room and R_CAP is not None and group and has_attr(group, "students_count"):
        cap = getattr(room, R_CAP.key)
        size = getattr(group, "students_count")
        if cap is not None and size is not None and size > cap:
            errors.append({"code": "room_capacity", "message": f"В группе {size} чел., аудитория вмещает {cap}."})

    # --- проверка компьютеров
    if require_computers and room and R_PC is not None and group and has_attr(group, "students_count"):
        pc = getattr(room, R_PC.key) or 0
        size = getattr(group, "students_count") or 0
        if pc < size:
            errors.append({"code": "room_computers", "message": f"Компьютеров {pc}, студентов {size}."})

    # --- базовый фильтр по времени
    time_filter = _overlap_q(date, slot_id=slot_id, start=start or order_no, end=end)

    # --- конфликты по аудитории
    if room_id and L_ROOM is not None:
        q = db.session.query(Lesson).filter(and_(time_filter, L_ROOM == room_id))
        if q.first():
            errors.append({"code": "room_busy", "message": "Аудитория занята в это время."})

    # --- конфликты по группе
    if group_id and L_GROUP is not None:
        q = db.session.query(Lesson).filter(and_(time_filter, L_GROUP == group_id))
        if q.first():
            errors.append({"code": "group_busy", "message": "У группы в это время уже есть занятие."})

    # --- конфликты по преподавателю
    if teacher_id and L_TEACH is not None:
        q = db.session.query(Lesson).filter(and_(time_filter, L_TEACH == teacher_id))
        if q.first():
            errors.append({"code": "teacher_busy", "message": "У преподавателя в это время уже есть занятие."})

    # --- предложения свободных аудиторий
    if Room is not None:
        free = []
        room_q = db.session.query(Room)
        for r in room_q.all():
            # отсекаем неподходящие по ёмкости/ПК
            if required_capacity is not None and R_CAP is not None:
                cap = getattr(r, R_CAP.key, None)
                if cap is not None and cap < required_capacity:
                    continue
            if require_computers and R_PC is not None and required_capacity is not None:
                pc = getattr(r, R_PC.key, 0) or 0
                if pc < required_capacity:
                    continue
            # занят ли?
            if L_ROOM is not None:
                busy = db.session.query(Lesson).filter(and_(time_filter, L_ROOM == getattr(r, "id"))).first()
                if busy:
                    continue
            free.append({"id": getattr(r, "id"), "label": getattr(r, "number", f"#{getattr(r, 'id')}")})
        suggestions["rooms"] = free[:10]

    return errors, warnings, suggestions
