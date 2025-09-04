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
    Возвращает занятия для группы за день (по умолчанию — сегодня) с автоматической вставкой «перерывов»
    между слотами, где отсутствуют пары. Не падает, если какие-то модели/поля ещё не готовы:
    вернёт мок-данные вместо 500.
    """
    from datetime import date as _date, datetime as _dt

    # --- параметры ---
    date_str = (request.args.get("date") or "").strip()
    range_mode = (request.args.get("range") or "day").strip().lower()  # пока поддерживаем day
    try:
        target_date = _dt.strptime(date_str, "%Y-%m-%d").date() if date_str else _date.today()
    except Exception:
        target_date = _date.today()

    # --- попытка боевой выборки из БД ---
    try:
        # Импорты моделей с мягкими фоллбэками имен
        try:
            from models.group import Group
        except Exception:
            Group = None
        try:
            from models.timeslot import TimeSlot
        except Exception:
            TimeSlot = None
        try:
            from models.lesson import Lesson
        except Exception:
            Lesson = None
        try:
            from models.teacher import Teacher
        except Exception:
            Teacher = None
        try:
            from models.subject import Subject
        except Exception:
            Subject = None
        try:
            from models.room import Room
        except Exception:
            Room = None
        try:
            from models.lesson_type import LessonType
        except Exception:
            LessonType = None
        try:
            from models.homework import Homework
        except Exception:
            Homework = None

        # Вспомогательные функции чтения атрибутов
        def _get(obj, *names, default=None):
            for n in names:
                if hasattr(obj, n):
                    return getattr(obj, n)
            return default

        # Ищем группу по code/name/label
        from extensions import db
        q = db.session.query(Group) if Group else None
        if q is None:
            raise RuntimeError("No Group model")
        # поддержим разные колонки кода/названия
        code_col = _get(Group, "code", "group_code", "name", "label")
        if code_col is None:
            raise RuntimeError("Group has no searchable code/name/label")
        group = q.filter(func.lower(code_col) == code.lower()).first()
        if not group:
            # допускаем частичное совпадение
            group = q.filter(func.lower(code_col).like(f"%{code.lower()}%")).first()
        if not group:
            raise RuntimeError("Group not found")

        # Получаем слоты дня (универсальные TimeSlot, не привязанные к дате)
        slots = []
        if TimeSlot:
            ts_order = _get(TimeSlot, "order_no", "order", "seq", "id")
            ts_start = _get(TimeSlot, "start_time", "start", "time_start")
            ts_end = _get(TimeSlot, "end_time", "end", "time_end")
            if ts_order and ts_start and ts_end:
                slots = (db.session.query(TimeSlot)
                         .order_by(ts_order.asc())
                         .all())
        # Получаем занятия на дату
        if not Lesson:
            raise RuntimeError("No Lesson model")

        # поля Lesson
        l_date = _get(Lesson, "date", "lesson_date", "day")
        l_group_id = _get(Lesson, "group_id", "groupId")
        l_group_rel = _get(Lesson, "group")
        l_timeslot_id = _get(Lesson, "time_slot_id", "timeslot_id", "slot_id")
        l_timeslot_rel = _get(Lesson, "time_slot", "timeslot", "slot")
        l_start = _get(Lesson, "start_time", "start")
        l_end = _get(Lesson, "end_time", "end")
        l_order = _get(Lesson, "order_no", "order", "seq")

        # связи
        l_subject_rel = _get(Lesson, "subject")
        l_subject_id  = _get(Lesson, "subject_id")
        l_teacher_rel = _get(Lesson, "teacher")
        l_teacher_id  = _get(Lesson, "teacher_id")
        l_room_rel    = _get(Lesson, "room")
        l_room_id     = _get(Lesson, "room_id")
        l_type_rel    = _get(Lesson, "lesson_type", "type")
        l_type_id     = _get(Lesson, "lesson_type_id", "type_id")
        l_is_remote   = _get(Lesson, "is_remote", "remote", "online")

        # Базовый запрос на занятия дня
        ql = db.session.query(Lesson)
        if l_date is not None:
            ql = ql.filter(l_date == target_date)
        if l_group_id is not None and hasattr(group, "id"):
            ql = ql.filter(l_group_id == group.id)
        elif l_group_rel is not None:
            ql = ql.filter(l_group_rel == group)

        # Сортировка по номеру слота или по времени
        order_cols = []
        if l_order is not None:
            order_cols.append(l_order.asc())
        elif l_start is not None:
            order_cols.append(l_start.asc())
        elif l_timeslot_id is not None:
            order_cols.append(l_timeslot_id.asc())
        ql = ql.order_by(*order_cols) if order_cols else ql

        rows = ql.all()

        # Функция получения времени слота/занятия
        def _resolve_times(l):
            # приоритет: слоты -> явные поля на Lesson
            start = end = None
            order_no = None
            slot_obj = None

            # через отношение на слот
            slot_obj = _get(l, "time_slot", "timeslot", "slot")
            if slot_obj:
                order_no = _get(slot_obj, "order_no", "order", "seq", "id")
                start = _get(slot_obj, "start_time", "start", "time_start")
                end   = _get(slot_obj, "end_time", "end", "time_end")

            # явные поля на Lesson (перекрывают)
            if l_start is not None:
                start = _get(l, "start_time", "start") or start
            if l_end is not None:
                end = _get(l, "end_time", "end") or end
            if l_order is not None:
                order_no = _get(l, "order_no", "order", "seq") or order_no

            # если всё ещё пусто и есть список slots
            if (start is None or end is None) and slots:
                # если есть timeslot_id
                slot_id_val = None
                if l_timeslot_id is not None:
                    slot_id_val = getattr(l, l_timeslot_id.key)
                # попробуем найти по id/порядку
                for s in slots:
                    s_id   = _get(s, "id")
                    s_ord  = _get(s, "order_no", "order", "seq", "id")
                    if (slot_id_val is not None and s_id == slot_id_val) or (order_no is not None and s_ord == order_no):
                        start = _get(s, "start_time", "start", "time_start")
                        end   = _get(s, "end_time", "end", "time_end")
                        break

            # приведение к строковому виду HH:MM (если это time/datetime)
            def _to_hhmm(v):
                if v is None:
                    return None
                if isinstance(v, str):
                    return v[:5]
                try:
                    return v.strftime("%H:%M")
                except Exception:
                    return str(v)[:5]

            return {
                "start_time": _to_hhmm(start) or "00:00",
                "end_time": _to_hhmm(end) or "00:00",
                "order_no": int(order_no) if isinstance(order_no, int) or (isinstance(order_no, str) and order_no.isdigit()) else order_no,
            }

        # Нормализация строки ФИО
        def _teacher_name(t):
            if not t:
                return "Преподаватель"
            fn = _get(t, "full_name")
            if fn:
                return fn
            parts = [ _get(t, "last_name","surname") , _get(t, "first_name","name"), _get(t, "middle_name","patronymic") ]
            return " ".join(p for p in parts if p).strip() or "Преподаватель"

        # Словарь слотов для поиска «перерывов»
        slots_map = {}
        for s in slots:
            s_ord = _get(s, "order_no", "order", "seq", "id")
            s_start = _get(s, "start_time", "start", "time_start")
            s_end = _get(s, "end_time", "end", "time_end")
            if s_ord is None:
                continue
            def _hhmm(v):
                if v is None:
                    return None
                if isinstance(v, str):
                    return v[:5]
                try:
                    return v.strftime("%H:%M")
                except Exception:
                    return str(v)[:5]
            slots_map[int(s_ord)] = (_hhmm(s_start) or "00:00", _hhmm(s_end) or "00:00")

        # Собираем занятия
        items = []
        seen_orders = set()
        for l in rows:
            times = _resolve_times(l)
            order_no = times["order_no"]
            if isinstance(order_no, str) and order_no.isdigit():
                order_no = int(order_no)

            # предмет
            subj = _get(l, "subject")
            if subj is None and Subject and l_subject_id is not None:
                subj = db.session.get(Subject, getattr(l, l_subject_id.key))
            subject_name = _get(subj, "name", "title", default="Дисциплина")

            # преподаватель
            tch = _get(l, "teacher")
            if tch is None and Teacher and l_teacher_id is not None:
                tch = db.session.get(Teacher, getattr(l, l_teacher_id.key))
            teacher_full = _teacher_name(tch)

            # аудитория
            room = _get(l, "room")
            if room is None and Room and l_room_id is not None:
                room = db.session.get(Room, getattr(l, l_room_id.key))
            room_number = _get(room, "number", "name", "code")

            # тип занятия
            ltype = _get(l, "lesson_type", "type")
            if ltype is None and LessonType and l_type_id is not None:
                ltype = db.session.get(LessonType, getattr(l, l_type_id.key))
            ltype_name = _get(ltype, "name", "title", default="Занятие")

            # дистанционно?
            is_remote = bool(getattr(l, l_is_remote.key)) if hasattr(l_is_remote, "key") else bool(_get(l, "is_remote", "remote", "online", default=False))

            # домашка (опционально)
            hw_obj = _get(l, "homework")
            hw_text = _get(hw_obj, "text") if hw_obj is not None else None

            items.append({
                "is_break": False,
                "subject": {"name": subject_name},
                "teacher": {"full_name": teacher_full},
                "time_slot": times,  # {"order_no","start_time","end_time"}
                "room": {"number": room_number} if room_number else None,
                "lesson_type": {"name": ltype_name},
                "is_remote": is_remote,
                "homework": {"text": hw_text} if hw_text else None,
            })
            if isinstance(order_no, int):
                seen_orders.add(order_no)

        # Вставляем «перерывы» по слотовой сетке: если есть slots_map
        if slots_map:
            # пройдёмся по всем слотам от мин до макс, добавим break для пропущенных
            if items:
                min_ord = min(slots_map.keys())
                max_ord = max(slots_map.keys())
                for ord_no in range(min_ord, max_ord + 1):
                    if ord_no not in seen_orders:
                        start, end = slots_map.get(ord_no, (None, None))
                        items.append({
                            "is_break": True,
                            "from": start or "—",
                            "to": end or "—",
                        })
                # сортировка: сначала по order_no, у break order_no нет — сортируем по времени начала
                def _key(x):
                    if x.get("is_break"):
                        return (x.get("from") or "00:00", 9999)
                    ts = x.get("time_slot") or {}
                    return (ts.get("start_time") or "00:00", ts.get("order_no") or 0)
                items.sort(key=_key)

        # Ответ
        return jsonify({
            "group_code": code,
            "date": target_date.isoformat(),
            "lessons": items
        })

    except Exception:
        # Фоллбек — прежние мок-данные (чтобы фронт работал, а мы могли донастроить модели позже)
        lessons = [
            {
                "is_break": False,
                "subject": {"name": "Высшая математика"},
                "teacher": {"full_name": "Иванов И.И."},
                "time_slot": {"order_no": 1, "start_time": "08:30", "end_time": "10:00"},
                "room": {"number": "101"},
                "lesson_type": {"name": "Лекция"},
                "is_remote": False,
                "homework": {"text": "Решить №1–5"},
            },
            {"is_break": True, "from": "10:00", "to": "10:20"},
            {
                "is_break": False,
                "subject": {"name": "Программирование"},
                "teacher": {"full_name": "Петров П.П."},
                "time_slot": {"order_no": 2, "start_time": "10:20", "end_time": "11:50"},
                "room": {"number": "Лаб-3"},
                "lesson_type": {"name": "Практика"},
                "is_remote": False,
                "homework": {"text": "Подготовить отчёт по ЛР-2"},
            },
            {
                "is_break": False,
                "subject": {"name": "История"},
                "teacher": {"full_name": "Сидорова А.В."},
                "time_slot": {"order_no": 3, "start_time": "12:10", "end_time": "13:40"},
                "room": None,
                "lesson_type": {"name": "Семинар"},
                "is_remote": True,
                "homework": None,
            },
        ]
        return jsonify({"group_code": code, "date": target_date.isoformat(), "lessons": lessons})
