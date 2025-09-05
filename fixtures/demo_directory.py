# fixtures/demo_directory.py
import os
import sys
from datetime import time

# добавить корень проекта в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from extensions import db
from models import (
    Building, RoomType, Room,
    Group, Teacher, Subject,
    LessonType, TimeSlot,
)

def get_or_create(model, defaults=None, **filters):
    inst = db.session.query(model).filter_by(**filters).first()
    if inst:
        return inst, False
    data = dict(filters)
    if defaults:
        data.update(defaults)
    inst = model(**data)
    db.session.add(inst)
    return inst, True

app = create_app("dev")
with app.app_context():
    spk, _ = get_or_create(Building, name="СПО корпус", defaults={"address": "ул. Учебная, 1", "type": "СПО"})
    bok, _ = get_or_create(Building, name="ВО корпус",  defaults={"address": "пр. Академический, 5", "type": "ВО"})

    rt_class, _ = get_or_create(RoomType, name="Обычная",      defaults={"requires_computers": False, "sports": False})
    rt_pc, _    = get_or_create(RoomType, name="Компьютерный", defaults={"requires_computers": True,  "sports": False})

    get_or_create(Room, building_id=spk.id, number="101",
                  defaults={"capacity": 30, "room_type_id": rt_class.id, "computers_count": 0})
    get_or_create(Room, building_id=spk.id, number="102",
                  defaults={"capacity": 30, "room_type_id": rt_pc.id,    "computers_count": 25})
    get_or_create(Room, building_id=bok.id, number="201",
                  defaults={"capacity": 50, "room_type_id": rt_class.id, "computers_count": 0})

    get_or_create(Group, code="ИТ-101",
                  defaults={"name": "Информатика 1 курс", "students_count": 28, "education_level": "СПО"})
    get_or_create(Group, code="ФК-201",
                  defaults={"name": "Физкультура 2 курс", "students_count": 24, "education_level": "СПО"})

    get_or_create(Teacher, full_name="Иванов И.И.", defaults={"short_name": "Иванов"})
    get_or_create(Teacher, full_name="Петров П.П.", defaults={"short_name": "Петров"})

    get_or_create(Subject, name="Математика",       defaults={"short_name": "Мат."})
    get_or_create(Subject, name="Программирование", defaults={"short_name": "Прог."})

    get_or_create(LessonType, name="Лекция")
    get_or_create(LessonType, name="Практика")

    get_or_create(TimeSlot, order_no=1, defaults={"start_time": time(8, 30),  "end_time": time(10, 0)})
    get_or_create(TimeSlot, order_no=2, defaults={"start_time": time(10, 10), "end_time": time(11, 40)})
    get_or_create(TimeSlot, order_no=3, defaults={"start_time": time(12, 20), "end_time": time(13, 50)})

    db.session.commit()
    print("✅ Demo directory data inserted/updated.")
