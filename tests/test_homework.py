# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date, time, timedelta
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import (
    User, Teacher, Group, Subject, LessonType, TimeSlot, Schedule, Homework
)

@pytest.fixture()
def app_ctx():
    app = create_app("dev")
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        HOMEWORK_ALLOW_PAST=False,
        HOMEWORK_ADMIN_OVERRIDE=True,
    )
    with app.app_context():
        db.create_all()
        # словари
        t1 = Teacher(full_name="Иванов И.И.", short_name="Иванов")
        t2 = Teacher(full_name="Петров П.П.", short_name="Петров")
        g = Group(code="ИТ-101", name="Инф", students_count=20, education_level="СПО")
        s = Subject(name="Программирование", short_name="Прог")
        lt = LessonType(name="Лекция")
        ts1 = TimeSlot(order_no=1, start_time=time(8,30), end_time=time(10,0))
        db.session.add_all([t1, t2, g, s, lt, ts1]); db.session.commit()
        # пользователи
        u_t1 = User(email="t1@example.com", password_hash=generate_password_hash("pass"), role="TEACHER", teacher_id=t1.id, is_active=True)
        u_admin = User(email="adm@example.com", password_hash=generate_password_hash("admin"), role="ADMIN", is_active=True)
        db.session.add_all([u_t1, u_admin]); db.session.commit()
        # пары: будущая и прошедшая
        future_day = date.today() + timedelta(days=7)
        past_day = date(2000, 1, 1)
        sch_future = Schedule(date=future_day, time_slot_id=ts1.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t1.id, room_id=None, is_remote=False)
        sch_past   = Schedule(date=past_day,   time_slot_id=ts1.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t1.id, room_id=None, is_remote=False)
        sch_other  = Schedule(date=future_day, time_slot_id=ts1.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t2.id, room_id=None, is_remote=False)
        db.session.add_all([sch_future, sch_past, sch_other]); db.session.commit()
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
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 200

def test_create_update_homework_success(client):
    login_as(client, "t1@example.com", "pass")
    token = csrf(client)

    # создаём
    r = client.post("/api/v1/homework", json={"lesson_id": 1, "text": "Сделать задачи 1-5", "deadline": "2099-01-01"},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 200
    js = r.get_json()
    assert js["ok"] is True
    assert js["homework"]["schedule_id"] == 1
    assert js["homework"]["deadline"] == "2099-01-01"

    # обновляем
    token = csrf(client)
    r2 = client.post("/api/v1/homework", json={"lesson_id": 1, "text": "Обновлено"},
                     headers={"X-CSRF-Token": token})
    assert r2.status_code == 200
    js2 = r2.get_json()
    assert js2["homework"]["text"] == "Обновлено"

def test_homework_not_owner_forbidden(client):
    login_as(client, "t1@example.com", "pass")
    token = csrf(client)
    # пара принадлежит другому преподавателю (id=3)
    r = client.post("/api/v1/homework", json={"lesson_id": 3, "text": "Нет прав"},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 403
    assert r.get_json()["error"] in ("not_owner", "forbidden")

def test_homework_past_denied_by_default(client):
    login_as(client, "t1@example.com", "pass")
    token = csrf(client)
    # прошедшая пара (id=2)
    r = client.post("/api/v1/homework", json={"lesson_id": 2, "text": "поздно"},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 400
    assert r.get_json()["error"] == "past_lesson_not_allowed"

def test_homework_visible_in_schedule_api(client):
    # создаём как преподаватель
    login_as(client, "t1@example.com", "pass")
    token = csrf(client)
    r = client.post("/api/v1/homework", json={"lesson_id": 1, "text": "HW in schedule"},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 200

    # теперь открываем API расписания преподавателя
    r2 = client.get("/api/v1/schedule/teacher/1?date=2099-01-01&range=week")
    # дата вне диапазона? Возьмём ближайшую неделю от сегодня, пара в +7 дней — попадёт
    if r2.status_code == 404:  # на случай иной реализации
        # попробуем без параметров
        r2 = client.get("/api/v1/schedule/teacher/1")
    assert r2.status_code == 200
    js = r2.get_json()
    # найдём нашу пару id=1
    items = [l for l in js["lessons"] if not l.get("is_break") and l.get("id") == 1]
    assert items, "lesson not found in schedule json"
    assert items[0].get("homework") and items[0]["homework"]["text"] == "HW in schedule"
