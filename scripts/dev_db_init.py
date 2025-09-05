# scripts/dev_init_db.py
from datetime import time
from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import (
    Building, RoomType, Room, TimeSlot,
    Group, Teacher, Subject, LessonType,
    User
)

def seed_minimal():
    b = Building.query.filter_by(name="MAIN").first()
    if not b:
        b = Building(name="MAIN", address="ул. Пример, 1", type="СПО")
        db.session.add(b)

    rt = RoomType.query.filter_by(name="Класс").first()
    if not rt:
        rt = RoomType(name="Класс", requires_computers=False)
        db.session.add(rt)

    db.session.flush()

    if not Room.query.filter_by(number="101").first():
        db.session.add(Room(building_id=b.id, number="101", capacity=30, room_type_id=rt.id, computers_count=0))

    if not TimeSlot.query.filter_by(order_no=1).first():
        db.session.add(TimeSlot(order_no=1, start_time=time(8,30), end_time=time(10,0)))
    if not TimeSlot.query.filter_by(order_no=2).first():
        db.session.add(TimeSlot(order_no=2, start_time=time(10,10), end_time=time(11,40)))

    if not Group.query.filter_by(code="G-1").first():
        db.session.add(Group(code="G-1", name="Группа 1", students_count=20, education_level="СПО"))

    if not Teacher.query.filter_by(full_name="Иван Иванов").first():
        db.session.add(Teacher(full_name="Иван Иванов", short_name="ИвИв"))

    if not Subject.query.filter_by(name="Математика").first():
        db.session.add(Subject(name="Математика", short_name="МАТ"))

    if not LessonType.query.filter_by(name="Лекция").first():
        db.session.add(LessonType(name="Лекция"))

    # Админ для входа
    if not User.query.filter_by(email="admin@example.com").first():
        db.session.add(User(
            email="admin@example.com",
            role="ADMIN",
            password_hash=generate_password_hash("pass")
        ))

    db.session.commit()

if __name__ == "__main__":
    app = create_app("dev")
    with app.app_context():
        db.create_all()
        seed_minimal()
        print("DB initialized and seeded ✅")
