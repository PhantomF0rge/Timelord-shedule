from flask import request, jsonify
from sqlalchemy import func, or_
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
    # допускаем поля code/name/label — берём что есть
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
    query = db.session.query(Group).filter(or_(*filters)).order_by(*(c.asc() for c in [code_col or name_col] if c is not None)).limit(limit)
    for g in query.all():
        # пробуем извлечь код/название из доступных атрибутов
        code = getattr(g, "code", None)
        name = getattr(g, "name", None)
        label = getattr(g, "label", None)
        items.append({
            "type": "group",
            "id": getattr(g, "id", None),
            "label": name or label or code or "Группа",
            "code": code or (name or label)  # фронту важен code для сохранения в localStorage
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
    # поддержим разные схемы ФИО
    for attr in ("full_name", "last_name", "first_name", "middle_name"):
        col = getattr(Teacher, attr, None)
        if col is not None:
            fields.append(col)
    if not fields:
        return items
    filters = [ _like(col, q) for col in fields ]
    query = db.session.query(Teacher).filter(or_(*filters)).limit(limit)
    for t in query.all():
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
    query = db.session.query(Subject).filter(_like(field, q)).limit(limit)
    for s in query.all():
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
    Ищет по БД. Если какая-то модель отсутствует — просто пропускаем её.
    """
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 10)
    only_type = (request.args.get("type") or "").strip().lower()

    if not q:
        return jsonify({"items": []})

    items = []
    # порядок: группы → преподаватели → дисциплины
    if not only_type or only_type == "group":
        items += _collect_group(q, limit)
    if (not only_type or only_type == "teacher") and len(items) < limit:
        items += _collect_teacher(q, limit - len(items))
    if (not only_type or only_type == "subject") and len(items) < limit:
        items += _collect_subject(q, limit - len(items))

    # safety: не больше limit
    return jsonify({"items": items[:limit]})


# ---------- SCHEDULE (пока прежний мок — заменим следующим шагом) ----------

@bp.get("/schedule/group/<code>")
def schedule_group(code: str):
    """
    GET /api/v1/schedule/group/<code>?date=YYYY-MM-DD&range=day|week
    Следующим PR заменим на реальные данные и автоматическую вставку «перерывов».
    """
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
    return jsonify({"group_code": code, "lessons": lessons})
