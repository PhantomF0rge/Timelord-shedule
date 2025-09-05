# tests/test_reports.py
from datetime import date, time, timedelta
import pytest

from app import create_app
from extensions import db
from werkzeug.security import generate_password_hash
from models import (
    Group, Teacher, Subject, LessonType,
    Building, RoomType, Room, TimeSlot, Schedule, User
)

def _csrf(client):
    r = client.get("/api/v1/csrf")
    return (r.get_json() or {}).get("csrf", "")

def _login_admin(client):
    if not User.query.filter_by(email="admin@example.com").first():
        db.session.add(User(email="admin@example.com", role="ADMIN",
                            password_hash=generate_password_hash("pass")))
        db.session.commit()
    t = _csrf(client)
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "pass"},
                    headers={"X-CSRF-Token": t})
    assert r.status_code == 200

@pytest.fixture()
def client():
    app = create_app("dev")
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()

        b = Building.query.filter_by(name="REP-B").first()
        if not b:
            b = Building(name="REP-B", address="x", type="СПО"); db.session.add(b); db.session.flush()

        rt = RoomType.query.filter_by(name="REP-RT").first()
        if not rt:
            rt = RoomType(name="REP-RT", requires_computers=False); db.session.add(rt); db.session.flush()

        r1 = Room.query.filter_by(number="REP-101").first()
        if not r1:
            r1 = Room(building_id=b.id, number="REP-101", capacity=30, room_type_id=rt.id, computers_count=0)
            db.session.add(r1)

        ts1 = TimeSlot.query.filter_by(order_no=901).first()
        if not ts1:
            ts1 = TimeSlot(order_no=901, start_time=time(8,30), end_time=time(10,0)); db.session.add(ts1)
        ts2 = TimeSlot.query.filter_by(order_no=902).first()
        if not ts2:
            ts2 = TimeSlot(order_no=902, start_time=time(10,10), end_time=time(11,40)); db.session.add(ts2)

        g = Group.query.filter_by(code="REP-G").first()
        if not g:
            g = Group(code="REP-G", name="Rep Group", students_count=20, education_level="СПО"); db.session.add(g)

        t = Teacher.query.filter_by(full_name="REP-T").first()
        if not t:
            t = Teacher(full_name="REP-T", short_name="RT"); db.session.add(t)

        s = Subject.query.filter_by(name="REP-S").first()
        if not s:
            s = Subject(name="REP-S", short_name="RS"); db.session.add(s)

        lt = LessonType.query.filter_by(name="REP-LT").first()
        if not lt:
            lt = LessonType(name="REP-LT"); db.session.add(lt)

        db.session.flush()

        today = date.today()
        tomorrow = today + timedelta(days=1)

        # две пары: сегодня/завтра, два разных слота
        if not Schedule.query.first():
            db.session.add(Schedule(date=today, time_slot_id=ts1.id, group_id=g.id,
                                    subject_id=s.id, lesson_type_id=lt.id, teacher_id=t.id, room_id=r1.id))
            db.session.add(Schedule(date=tomorrow, time_slot_id=ts2.id, group_id=g.id,
                                    subject_id=s.id, lesson_type_id=lt.id, teacher_id=t.id, room_id=r1.id))
        db.session.commit()

        yield app.test_client()

def test_weekly_schedule_group(client):
    _login_admin(client)
    g = Group.query.filter_by(code="REP-G").first()
    d_from = date.today().isoformat()
    d_to = (date.today()+timedelta(days=1)).isoformat()
    r = client.get(f"/api/v1/admin/reports/weekly-schedule.csv?scope=group&id={g.id}&date_from={d_from}&date_to={d_to}")
    assert r.status_code == 200
    text = r.data.decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0] == "date;weekday;slot_order;start;end;group_code;group_name;teacher;subject;lesson_type;room;building"
    # Должны быть хотя бы 2 строки данных
    assert len(lines) >= 3
    assert "REP-G" in lines[1] and "REP-T" in lines[1]

def test_teacher_hours_total(client):
    _login_admin(client)
    d_from = date.today().isoformat()
    d_to = (date.today()+timedelta(days=1)).isoformat()
    r = client.get(f"/api/v1/admin/reports/teacher-hours.csv?date_from={d_from}&date_to={d_to}")
    assert r.status_code == 200
    text = r.data.decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0] == "teacher_id;teacher;total_hours"
    # одна строка данных с суммой 3.00 (два слота по 1.5 часа)
    parts = lines[1].split(";")
    assert float(parts[2]) == 3.00

def test_room_utilization(client):
    _login_admin(client)
    b = Building.query.filter_by(name="REP-B").first()
    d_from = date.today().isoformat()
    d_to = (date.today()+timedelta(days=1)).isoformat()
    r = client.get(f"/api/v1/admin/reports/room-utilization.csv?date_from={d_from}&date_to={d_to}&building_id={b.id}")
    assert r.status_code == 200
    text = r.data.decode("utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0] == "building;room;slots_used;slots_total;hours_used;utilization_pct"
    # 2 дня * 2 слота = 4 total, занято 2 → 50.00%
    header = lines[1].split(";")
    assert header[0] == "REP-B"
    assert header[2] == "2"
    assert header[3] == "4"
    assert header[5] == "50.00"
