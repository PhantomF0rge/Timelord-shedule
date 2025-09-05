from __future__ import annotations
from datetime import date, time
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import (
    User, Teacher, Group, Subject, LessonType, TimeSlot, Schedule
)

@pytest.fixture()
def app_ctx():
    app = create_app("dev")
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.create_all()
        # словари / сущности
        t = Teacher(full_name="Иванов И.И.", short_name="Иванов")
        g = Group(code="ИТ-101", name="Инф", students_count=20, education_level="СПО")
        s = Subject(name="Программирование", short_name="Прог")
        lt = LessonType(name="Лекция")
        ts1 = TimeSlot(order_no=1, start_time=time(8,30), end_time=time(10,0))   # 1.5ч
        ts2 = TimeSlot(order_no=2, start_time=time(10,10), end_time=time(11,40)) # 1.5ч
        db.session.add_all([t,g,s,lt,ts1,ts2]); db.session.commit()
        # user-teacher
        u_teacher = User(email="teacher@example.com", password_hash=generate_password_hash("pass"), role="TEACHER", teacher_id=t.id, is_active=True)
        u_admin   = User(email="admin@example.com", password_hash=generate_password_hash("admin"), role="ADMIN", is_active=True)
        db.session.add_all([u_teacher, u_admin]); db.session.commit()

        # пары в неделе 2025-09-01..07 (Mon..Sun)
        d1 = date(2025, 9, 1)  # Mon
        d2 = date(2025, 9, 3)  # Wed
        # 3 пары: 2 в d1, 1 в d2 => рабочих дней 2, часов 4.5, пар 3
        sch1 = Schedule(date=d1, time_slot_id=ts1.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t.id, room_id=None, is_remote=False)
        sch2 = Schedule(date=d1, time_slot_id=ts2.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t.id, room_id=None, is_remote=True)
        sch3 = Schedule(date=d2, time_slot_id=ts2.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t.id, room_id=None, is_remote=False)
        db.session.add_all([sch1, sch2, sch3]); db.session.commit()

        yield app
        db.drop_all()

@pytest.fixture()
def client(app_ctx):
    return app_ctx.test_client()

def csrf(client):
    r = client.get("/api/v1/auth/csrf")
    assert r.status_code == 200
    return r.get_json()["csrf_token"]

def login_as(client, email, password):
    token = csrf(client)
    r = client.post("/api/v1/auth/login", json={"email":email, "password":password}, headers={"X-CSRF-Token": token})
    assert r.status_code == 200

def test_access_requires_login(client):
    r = client.get("/teacher/me")
    # в тестовом режиме LoginManager вернёт JSON 401
    assert r.status_code == 401

def test_access_forbidden_for_admin(client):
    login_as(client, "admin@example.com", "admin")
    r = client.get("/teacher/me")
    assert r.status_code == 403

def test_aggregate_week(client):
    login_as(client, "teacher@example.com", "pass")
    r = client.get("/api/v1/teacher/me/aggregate?date=2025-09-02&range=week")
    assert r.status_code == 200
    js = r.get_json()
    assert js["counts"]["work_days"] == 2
    assert js["counts"]["pairs"] == 3
    assert js["counts"]["hours"] == 4.5
    # уроки отсортированы
    ls = js["lessons"]
    assert ls[0]["date"] <= ls[-1]["date"]

def test_me_page_ok(client):
    login_as(client, "teacher@example.com", "pass")
    r = client.get("/teacher/me")
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    assert "Моё расписание" in text
