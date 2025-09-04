"""
Idempotent seed-скрипт.
Запуск:
  python seed.py --reset         # дропнуть и пересоздать БД + демо-данные + admin/admin
  python seed.py --ensure-admin  # создать только пользователя admin/admin (без сидов)
  python seed.py                 # мягкое наполнение недостающих данных (idempotent)
"""
from datetime import date, time
import argparse
from sqlalchemy import func, and_

from app import create_app
from extensions import db

# ---- безопасные импорты моделей (разные имена файлов поддерживаются) ----
def _safe_import(path, name):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name, None)
    except Exception:
        return None

Group      = _safe_import("models.group", "Group") or _safe_import("models.groups", "Group")
Teacher    = _safe_import("models.teacher", "Teacher") or _safe_import("models.teachers", "Teacher")
Subject    = _safe_import("models.subject", "Subject") or _safe_import("models.subjects", "Subject")
Building   = _safe_import("models.building", "Building")
RoomType   = _safe_import("models.room_type", "RoomType") or _safe_import("models.roomtype", "RoomType")
Room       = _safe_import("models.room", "Room") or _safe_import("models.rooms", "Room")
LessonType = _safe_import("models.lesson_type", "LessonType") or _safe_import("models.lesson_types", "LessonType")
TimeSlot   = _safe_import("models.timeslot", "TimeSlot") or _safe_import("models.time_slot", "TimeSlot")
Lesson     = _safe_import("models.lesson", "Lesson") or _safe_import("models.lessons", "Lesson")
Homework   = _safe_import("models.homework", "Homework") or _safe_import("models.homeworks", "Homework")
User       = _safe_import("models.user", "User")

# ---- вспомогательные утилиты ----
def has_attr(obj_or_cls, name: str) -> bool:
    try:
        return hasattr(obj_or_cls, name)
    except Exception:
        return False

def build_kwargs(obj_cls, **kwargs):
    """Возвращает только те поля, которые реально есть у модели."""
    out = {}
    for k, v in kwargs.items():
        if has_attr(obj_cls, k):
            out[k] = v
    return out

def first_by(model, **criteria):
    """Безопасно фильтрует по существующим полям."""
    q = db.session.query(model)
    conds = []
    for k, v in criteria.items():
        if has_attr(model, k):
            conds.append(getattr(model, k) == v)
    if not conds:
        return None
    return q.filter(and_(*conds)).first()

def get_or_create(model, defaults=None, **by):
    """Идемпотентное создание по уникальным ключам."""
    inst = first_by(model, **by)
    if inst:
        return inst, False
    data = {}
    if defaults:
        data.update(defaults)
    data.update(by)
    inst = model(**build_kwargs(model, **data))
    db.session.add(inst)
    db.session.flush()
    return inst, True

# ---- сиды справочников ----
def seed_base_dicts():
    """Создаёт/находит: группу, преподавателей, предметы, корпуса, типы ауд., аудитории, типы занятий, тайм-слоты."""
    ids = {}

    # Group (уникально по code)
    if Group is not None:
        grp, _ = get_or_create(
            Group,
            code="PI-101",
            name="ПИ-101",
            students_count=30,
            education_level="СПО",
            label="ПИ-101",
        )
        ids["group_id"] = getattr(grp, "id", None)

    # Teachers (уникально по full_name)
    if Teacher is not None:
        t1, _ = get_or_create(Teacher,
                              full_name="Иванов И.И.",
                              defaults=dict(last_name="Иванов", first_name="Иван", middle_name="Иванович"))
        t2, _ = get_or_create(Teacher,
                              full_name="Петров П.П.",
                              defaults=dict(last_name="Петров", first_name="Пётр", middle_name="Петрович"))
        ids["teacher_ivanov_id"] = getattr(t1, "id", None)
        ids["teacher_petrov_id"] = getattr(t2, "id", None)

    # Subjects (уникально по name)
    if Subject is not None:
        s1, _ = get_or_create(Subject, name="Высшая математика", defaults=dict(title="Высшая математика"))
        s2, _ = get_or_create(Subject, name="Программирование", defaults=dict(title="Программирование"))
        s3, _ = get_or_create(Subject, name="История", defaults=dict(title="История"))
        ids["subj_math_id"] = getattr(s1, "id", None)
        ids["subj_prog_id"] = getattr(s2, "id", None)
        ids["subj_hist_id"] = getattr(s3, "id", None)

    # Buildings (уникально по code, либо по name)
    if Building is not None:
        if has_attr(Building, "code"):
            b1, _ = get_or_create(Building, code="A", defaults=dict(name="Главный корпус", title="Главный корпус", address=""))
        else:
            b1, _ = get_or_create(Building, name="Главный корпус", defaults=dict(title="Главный корпус", address=""))
        ids["building_main_id"] = getattr(b1, "id", None)

    # Room Types (уникально по name)
    if RoomType is not None:
        rt1, _ = get_or_create(RoomType, name="lecture", defaults=dict(title="Лекционная"))
        rt2, _ = get_or_create(RoomType, name="computer", defaults=dict(title="Компьютерный класс"))
        ids["rt_lecture_id"] = getattr(rt1, "id", None)
        ids["rt_computer_id"] = getattr(rt2, "id", None)

    # Rooms (уникально по (building_id, number) если есть FK, иначе по number)
    if Room is not None:
        # 101
        r1_by = {"number": "101"}
        if has_attr(Room, "building_id"):
            r1_by["building_id"] = ids.get("building_main_id")
        r1_defaults = dict(capacity=40, computers_count=0, computers=0)
        if has_attr(Room, "room_type_id"):
            r1_defaults["room_type_id"] = ids.get("rt_lecture_id")
        r1, _ = get_or_create(Room, defaults=r1_defaults, **r1_by)

        # Лаб-3
        r2_by = {"number": "Лаб-3"}
        if has_attr(Room, "building_id"):
            r2_by["building_id"] = ids.get("building_main_id")
        r2_defaults = dict(capacity=25, computers_count=25, computers=25)
        if has_attr(Room, "room_type_id"):
            r2_defaults["room_type_id"] = ids.get("rt_computer_id")
        r2, _ = get_or_create(Room, defaults=r2_defaults, **r2_by)

        ids["room_101_id"] = getattr(r1, "id", None)
        ids["room_lab3_id"] = getattr(r2, "id", None)

    # Lesson Types (уникально по name)
    if LessonType is not None:
        lt1, _ = get_or_create(LessonType, name="Лекция", defaults=dict(title="Лекция"))
        lt2, _ = get_or_create(LessonType, name="Практика", defaults=dict(title="Практика"))
        lt3, _ = get_or_create(LessonType, name="Семинар", defaults=dict(title="Семинар"))
        ids["lt_lecture_id"] = getattr(lt1, "id", None)
        ids["lt_practice_id"] = getattr(lt2, "id", None)
        ids["lt_seminar_id"] = getattr(lt3, "id", None)

    # TimeSlots (уникально по order_no или order)
    if TimeSlot is not None:
        def slot(by_order, start, end):
            if has_attr(TimeSlot, "order_no"):
                s, _ = get_or_create(TimeSlot, order_no=by_order,
                                     defaults=dict(order=by_order, start_time=start, end_time=end))
            elif has_attr(TimeSlot, "order"):
                s, _ = get_or_create(TimeSlot, order=by_order,
                                     defaults=dict(order_no=by_order, start_time=start, end_time=end))
            else:
                # нет полей порядка — привязываем по времени
                s, _ = get_or_create(TimeSlot, start_time=start, end_time=end, defaults=dict(order_no=by_order))
            return s

        ts1 = slot(1, time(8,30),  time(10,0))
        ts2 = slot(2, time(10,20), time(11,50))
        ts3 = slot(3, time(12,10), time(13,40))

        def ord_no(ts):
            return getattr(ts, "order_no", getattr(ts, "order", 0))
        ids["slot1_id"] = getattr(ts1, "id", None); ids["slot1_ord"] = ord_no(ts1)
        ids["slot2_id"] = getattr(ts2, "id", None); ids["slot2_ord"] = ord_no(ts2)
        ids["slot3_id"] = getattr(ts3, "id", None); ids["slot3_ord"] = ord_no(ts3)

    db.session.commit()
    return ids

# ---- уроки + домашка (идемпотентно) ----
def seed_lessons_today(ids):
    if Lesson is None:
        return
    today = date.today()

    def lesson_exists(order_no):
        q = db.session.query(Lesson)
        conds = []
        if has_attr(Lesson, "date"):
            conds.append(Lesson.date == today)
        if has_attr(Lesson, "group_id") and ids.get("group_id"):
            conds.append(Lesson.group_id == ids["group_id"])
        if has_attr(Lesson, "order_no") and order_no is not None:
            conds.append(Lesson.order_no == order_no)
        if not conds:
            return None
        return q.filter(and_(*conds)).first()

    def new_lesson(slot_id=None, order_no=None, subj_id=None, teacher_id=None, room_id=None, ltype_id=None, is_remote=False):
        kw = {}
        # дата
        for f in ("date", "lesson_date", "day"):
            if has_attr(Lesson, f): kw[f] = today
        # связи
        if has_attr(Lesson, "group_id"): kw["group_id"] = ids.get("group_id")
        if has_attr(Lesson, "time_slot_id"): kw["time_slot_id"] = slot_id
        if has_attr(Lesson, "subject_id"): kw["subject_id"] = subj_id
        if has_attr(Lesson, "teacher_id"): kw["teacher_id"] = teacher_id
        if has_attr(Lesson, "room_id"): kw["room_id"] = room_id
        if has_attr(Lesson, "lesson_type_id"): kw["lesson_type_id"] = ltype_id
        # порядок/время
        if has_attr(Lesson, "order_no"): kw["order_no"] = order_no
        if has_attr(Lesson, "order"): kw["order"] = order_no
        # дистанционно
        for f in ("is_remote", "remote", "online"):
            if has_attr(Lesson, f): kw[f] = is_remote
        return Lesson(**build_kwargs(Lesson, **kw))

    # 1-я пара
    if not lesson_exists(ids.get("slot1_ord")):
        l1 = new_lesson(ids.get("slot1_id"), ids.get("slot1_ord"), ids.get("subj_math_id"),
                        ids.get("teacher_ivanov_id"), ids.get("room_101_id"), ids.get("lt_lecture_id"), False)
        db.session.add(l1); db.session.flush()
        if Homework is not None:
            db.session.add(Homework(**build_kwargs(Homework, text="Решить №1–5", lesson_id=getattr(l1, "id", None))))

    # 2-я пара
    if not lesson_exists(ids.get("slot2_ord")):
        l2 = new_lesson(ids.get("slot2_id"), ids.get("slot2_ord"), ids.get("subj_prog_id"),
                        ids.get("teacher_petrov_id"), ids.get("room_lab3_id"), ids.get("lt_practice_id"), False)
        db.session.add(l2); db.session.flush()
        if Homework is not None:
            db.session.add(Homework(**build_kwargs(Homework, text="Подготовить отчёт по ЛР-2", lesson_id=getattr(l2, "id", None))))

    # 3-я пара (СДО)
    if not lesson_exists(ids.get("slot3_ord")):
        l3 = new_lesson(ids.get("slot3_id"), ids.get("slot3_ord"), ids.get("subj_hist_id"),
                        ids.get("teacher_ivanov_id"), None, ids.get("lt_seminar_id"), True)
        db.session.add(l3); db.session.flush()

    db.session.commit()

# ---- админ ----
def ensure_admin():
    if User is None:
        return False
    exists = db.session.query(User).filter(func.lower(User.username) == "admin").first()
    if exists:
        return False
    u = User(username="admin", role="admin")
    u.set_password("admin")
    db.session.add(u)
    db.session.commit()
    return True

# ---- main ----
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop + create + full seed (demo)")
    parser.add_argument("--ensure-admin", action="store_true", help="create only admin/admin")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.reset:
            try:
                db.drop_all()
            except Exception:
                pass
            db.create_all()
            ids = seed_base_dicts()
            seed_lessons_today(ids)
            ensure_admin()
            print("[seed] reset+seed complete")
            return

        if args.ensure_admin:
            created = ensure_admin()
            print("Admin created." if created else "Admin already exists.")
            return

        # режим по умолчанию — мягкое наполнение недостающих данных
        db.create_all()
        ids = seed_base_dicts()
        seed_lessons_today(ids)
        print("[seed] soft seed complete")

if __name__ == "__main__":
    main()
