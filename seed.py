"""
Seed-скрипт для быстрого разворота БД локально.
Запуск:
  python seed.py --reset   # дропнуть таблицы (если можно) и создать заново
  python seed.py           # только создать недостающие и наполнить демо-данными

Скрипт максимально "мягкий": выставляет только те поля, что реально есть в моделях.
Если какие-то модели/поля отличаются именами — он их пропустит, но остальное заполнит.
"""

from datetime import date, time
import argparse

from app import create_app
from extensions import db

# Пытаемся импортировать модели (если чего-то нет — оставляем None, скрипт это переживёт)
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
LessonType = _safe_import("models.lesson_type", "LessonType")
TimeSlot   = _safe_import("models.timeslot", "TimeSlot")
Lesson     = _safe_import("models.lesson", "Lesson")
Homework   = _safe_import("models.homework", "Homework")

def has_attr(obj_or_cls, name: str) -> bool:
    try:
        return hasattr(obj_or_cls, name)
    except Exception:
        return False

def build_kwargs(obj_cls, **kwargs):
    """Вернёт dict только с теми полями, которые реально существуют у модели."""
    out = {}
    for k, v in kwargs.items():
        if has_attr(obj_cls, k):
            out[k] = v
    return out

def set_if_has(obj, **kwargs):
    for k, v in kwargs.items():
        if has_attr(obj, k):
            setattr(obj, k, v)

def seed_base_dicts():
    """Создаёт справочники: группы, преподаватели, предметы, аудитории, типы, слоты."""
    ids = {}

    # --- Group ---
    if Group is not None:
        grp = Group(**build_kwargs(
            Group,
            code="PI-101",
            name="ПИ-101",
            students_count=30,
            education_level="СПО",
            label="ПИ-101",
        ))
        db.session.add(grp); db.session.flush()
        ids["group_id"] = getattr(grp, "id", None)

    # --- Teachers ---
    if Teacher is not None:
        t1 = Teacher(**build_kwargs(Teacher, full_name="Иванов И.И.", last_name="Иванов", first_name="Иван", middle_name="Иванович"))
        t2 = Teacher(**build_kwargs(Teacher, full_name="Петров П.П.", last_name="Петров", first_name="Пётр", middle_name="Петрович"))
        db.session.add_all([t1, t2]); db.session.flush()
        ids["teacher_ivanov_id"] = getattr(t1, "id", None)
        ids["teacher_petrov_id"] = getattr(t2, "id", None)

    # --- Subjects ---
    if Subject is not None:
        s1 = Subject(**build_kwargs(Subject, name="Высшая математика", title="Высшая математика"))
        s2 = Subject(**build_kwargs(Subject, name="Программирование", title="Программирование"))
        s3 = Subject(**build_kwargs(Subject, name="История", title="История"))
        db.session.add_all([s1, s2, s3]); db.session.flush()
        ids["subj_math_id"] = getattr(s1, "id", None)
        ids["subj_prog_id"] = getattr(s2, "id", None)
        ids["subj_hist_id"] = getattr(s3, "id", None)

    # --- Rooms ---
    if Room is not None:
        r1 = Room(**build_kwargs(Room, number="101", capacity=40, computers=0, room_type="lecture"))
        r2 = Room(**build_kwargs(Room, number="Лаб-3", capacity=25, computers=25, room_type="computer"))
        db.session.add_all([r1, r2]); db.session.flush()
        ids["room_101_id"] = getattr(r1, "id", None)
        ids["room_lab3_id"] = getattr(r2, "id", None)

    # --- Lesson Types ---
    if LessonType is not None:
        lt1 = LessonType(**build_kwargs(LessonType, name="Лекция", title="Лекция"))
        lt2 = LessonType(**build_kwargs(LessonType, name="Практика", title="Практика"))
        lt3 = LessonType(**build_kwargs(LessonType, name="Семинар", title="Семинар"))
        db.session.add_all([lt1, lt2, lt3]); db.session.flush()
        ids["lt_lecture_id"] = getattr(lt1, "id", None)
        ids["lt_practice_id"] = getattr(lt2, "id", None)
        ids["lt_seminar_id"] = getattr(lt3, "id", None)

    # --- TimeSlots ---
    if TimeSlot is not None:
        ts1 = TimeSlot(**build_kwargs(TimeSlot, order_no=1, order=1, start_time=time(8,30),  end_time=time(10,0)))
        ts2 = TimeSlot(**build_kwargs(TimeSlot, order_no=2, order=2, start_time=time(10,20), end_time=time(11,50)))
        ts3 = TimeSlot(**build_kwargs(TimeSlot, order_no=3, order=3, start_time=time(12,10), end_time=time(13,40)))
        db.session.add_all([ts1, ts2, ts3]); db.session.flush()
        # сохраняем id/порядки
        ids["slot1_id"] = getattr(ts1, "id", None); ids["slot1_ord"] = getattr(ts1, "order_no", getattr(ts1, "order", 1))
        ids["slot2_id"] = getattr(ts2, "id", None); ids["slot2_ord"] = getattr(ts2, "order_no", getattr(ts2, "order", 2))
        ids["slot3_id"] = getattr(ts3, "id", None); ids["slot3_ord"] = getattr(ts3, "order_no", getattr(ts3, "order", 3))

    db.session.commit()
    return ids

def seed_lessons_today(ids):
    """Создаёт демо-занятия на сегодняшнюю дату для группы PI-101, включая ДЗ и дистанционную пару."""
    if Lesson is None:
        return
    today = date.today()

    # Помощники для kwargs
    def lesson_kwargs(slot_id=None, order_no=None, subj_id=None, teacher_id=None, room_id=None, ltype_id=None, is_remote=False, start=None, end=None):
        kw = dict()
        # дата
        if has_attr(Lesson, "date"): kw["date"] = today
        if has_attr(Lesson, "lesson_date"): kw["lesson_date"] = today
        if has_attr(Lesson, "day"): kw["day"] = today
        # связи/ключи
        if has_attr(Lesson, "group_id"): kw["group_id"] = ids.get("group_id")
        if has_attr(Lesson, "time_slot_id"): kw["time_slot_id"] = slot_id
        if has_attr(Lesson, "subject_id"): kw["subject_id"] = subj_id
        if has_attr(Lesson, "teacher_id"): kw["teacher_id"] = teacher_id
        if has_attr(Lesson, "room_id"): kw["room_id"] = room_id
        if has_attr(Lesson, "lesson_type_id"): kw["lesson_type_id"] = ltype_id
        # флаги
        if has_attr(Lesson, "is_remote"): kw["is_remote"] = is_remote
        if has_attr(Lesson, "remote"): kw["remote"] = is_remote
        if has_attr(Lesson, "online"): kw["online"] = is_remote
        # альтернативы по времени/порядку
        if has_attr(Lesson, "order_no"): kw["order_no"] = order_no
        if has_attr(Lesson, "order"): kw["order"] = order_no
        if has_attr(Lesson, "start_time") and start is not None: kw["start_time"] = start
        if has_attr(Lesson, "end_time") and end is not None: kw["end_time"] = end
        return kw

    # Пары:
    l1 = Lesson(**lesson_kwargs(
        slot_id=ids.get("slot1_id"), order_no=ids.get("slot1_ord"),
        subj_id=ids.get("subj_math_id"), teacher_id=ids.get("teacher_ivanov_id"),
        room_id=ids.get("room_101_id"), ltype_id=ids.get("lt_lecture_id"),
        is_remote=False,
    ))
    l2 = Lesson(**lesson_kwargs(
        slot_id=ids.get("slot2_id"), order_no=ids.get("slot2_ord"),
        subj_id=ids.get("subj_prog_id"), teacher_id=ids.get("teacher_petrov_id"),
        room_id=ids.get("room_lab3_id"), ltype_id=ids.get("lt_practice_id"),
        is_remote=False,
    ))
    l3 = Lesson(**lesson_kwargs(
        slot_id=ids.get("slot3_id"), order_no=ids.get("slot3_ord"),
        subj_id=ids.get("subj_hist_id"), teacher_id=ids.get("teacher_ivanov_id"),
        room_id=None, ltype_id=ids.get("lt_seminar_id"),
        is_remote=True,
    ))

    db.session.add_all([l1, l2, l3]); db.session.flush()

    # Домашки (если есть модель/связи)
    if Homework is not None:
        hw1 = Homework(**build_kwargs(Homework, text="Решить №1–5", lesson_id=getattr(l1, "id", None)))
        hw2 = Homework(**build_kwargs(Homework, text="Подготовить отчёт по ЛР-2", lesson_id=getattr(l2, "id", None)))
        db.session.add_all([hw1, hw2])

    db.session.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop + create all tables before seeding")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.reset:
            try:
                db.drop_all()
            except Exception:
                # на SQLite drop_all может не удалить всё — игнорируем
                pass
        db.create_all()  # создаст недостающие таблицы
        ids = seed_base_dicts()
        seed_lessons_today(ids)

        print("[seed] done. Try:")
        print(" - http://127.0.0.1:5000/  (в поиске введите 'ПИ-101' и выберите)")
        print(" - GET /api/v1/suggest?q=пи")
        print(f" - GET /api/v1/schedule/group/PI-101?date={date.today().isoformat()}&range=day")

if __name__ == "__main__":
    main()
