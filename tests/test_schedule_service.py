from __future__ import annotations
from datetime import date, time, datetime
from zoneinfo import ZoneInfo
import pytest

from app import create_app
from extensions import db
from models import (
    Group, Teacher, Subject, RoomType, Building, Room,
    LessonType, TimeSlot, Schedule, Homework
)
from blueprints.schedule import services as svc

TZ = ZoneInfo("Europe/Berlin")

@pytest.fixture()
def app_ctx():
    app = create_app("dev")
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.create_all()
        # базовые словари
        g = Group(code="ИТ-101", name="Инф", students_count=20, education_level="СПО")
        t = Teacher(full_name="Иванов И.И.", short_name="Иванов")
        s = Subject(name="Программирование", short_name="Прог")
        lt = LessonType(name="Лекция")
        b = Building(name="СПО корпус", address="ул.1", type="СПО")
        rt = RoomType(name="Обычная")
        r = Room(building=b, number="101", capacity=30, room_type=rt, computers_count=0)
        ts1 = TimeSlot(order_no=1, start_time=time(8,30), end_time=time(10,0))
        ts2 = TimeSlot(order_no=2, start_time=time(10,10), end_time=time(11,40))
        ts3 = TimeSlot(order_no=3, start_time=time(12,20), end_time=time(13,50))
        db.session.add_all([g,t,s,lt,b,rt,r,ts1,ts2,ts3])
        db.session.commit()
        # пара в 1-й и 3-й слот, второй — «перерыв»
        d = date(2025, 9, 5)
        sch1 = Schedule(date=d, time_slot_id=ts1.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t.id, room_id=r.id, is_remote=False)
        sch3 = Schedule(date=d, time_slot_id=ts3.id, group_id=g.id, subject_id=s.id, lesson_type_id=lt.id, teacher_id=t.id, room_id=r.id, is_remote=True)
        db.session.add_all([sch1, sch3])
        db.session.commit()
        db.session.add(Homework(schedule_id=sch1.id, text="Прочитать главы 1-2"))
        db.session.commit()
        yield app
        db.drop_all()

def test_break_insertion_and_remote(app_ctx):
    now = datetime(2025, 9, 5, 9, 0, tzinfo=TZ)  # во время 1-й пары
    out = svc.schedule_for_group("ИТ-101", date(2025, 9, 5), "day", now_berlin=now)
    assert out["days"] and len(out["days"][0]["items"]) == 3
    items = out["days"][0]["items"]
    assert items[1]["is_break"] is True
    assert items[2]["is_remote"] is True  # 3-й слот СДО
    assert items[0]["status"] == "now"

def test_api_group_day(app_ctx):
    client = app_ctx.test_client()
    r = client.get("/api/v1/schedule/group/ИТ-101?date=2025-09-05&range=day")
    assert r.status_code == 200
    js = r.get_json()
    assert js["entity"]["type"] == "group"
    assert js["days"][0]["items"][1]["is_break"] is True

def test_lesson_details(app_ctx):
    # найдём id первого урока
    from models import Schedule
    sch = Schedule.query.first()
    client = app_ctx.test_client()
    r = client.get(f"/api/v1/lesson/{sch.id}")
    assert r.status_code == 200
    js = r.get_json()
    assert js["subject"] == "Программирование"
    assert js["group"] == "ИТ-101"
    assert isinstance(js["homework"], list) and js["homework"][0]["text"]
