import pytest
from app import create_app
from extensions import db
from werkzeug.security import generate_password_hash
from models import (
    Group, Teacher, Subject, LessonType,
    Building, RoomType, Room, TimeSlot,
    Schedule, User, AuditLog,
    WorkloadLimit, TeacherAvailability, Curriculum,
)

from datetime import date, time

def _csrf(client):
    r = client.get("/api/v1/csrf")
    return (r.get_json() or {}).get("csrf", "")

def _login_admin(client):
    # здесь уже есть app.app_context() благодаря фикстуре
    if not User.query.filter_by(email="admin@example.com").first():
        db.session.add(User(
            email="admin@example.com",
            role="ADMIN",
            password_hash=generate_password_hash("pass"),
        ))
        db.session.commit()

    token = _csrf(client)
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "pass"},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 200, r.get_json()
    return token  # вернём CSRF для последующих POST’ов

@pytest.fixture()
def client():
    app = create_app("dev")
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()

        # БАЗОВЫЕ СПРАВОЧНИКИ (get-or-create)
        b = Building.query.filter_by(name="E2E").first()
        if not b:
            b = Building(name="E2E", address="x", type="СПО")
            db.session.add(b); db.session.flush()

        rt = RoomType.query.filter_by(name="E2E-RT").first()
        if not rt:
            rt = RoomType(name="E2E-RT", requires_computers=False)
            db.session.add(rt); db.session.flush()

        r1 = Room.query.filter_by(number="E2E-101").first()
        if not r1:
            r1 = Room(building_id=b.id, number="E2E-101", capacity=30, room_type_id=rt.id, computers_count=0)
            db.session.add(r1)

        ts1 = TimeSlot.query.filter_by(order_no=801).first()
        if not ts1:
            ts1 = TimeSlot(order_no=801, start_time=time(8, 30), end_time=time(10, 0))
            db.session.add(ts1)
        ts2 = TimeSlot.query.filter_by(order_no=802).first()
        if not ts2:
            ts2 = TimeSlot(order_no=802, start_time=time(10, 10), end_time=time(11, 40))
            db.session.add(ts2)

        g = Group.query.filter_by(code="E2E-G").first()
        if not g:
            g = Group(code="E2E-G", name="E2E Group", students_count=20, education_level="СПО")
            db.session.add(g)

        t = Teacher.query.filter_by(full_name="E2E-T").first()
        if not t:
            t = Teacher(full_name="E2E-T", short_name="E2E")
            db.session.add(t)

        s = Subject.query.filter_by(name="E2E-S").first()
        if not s:
            s = Subject(name="E2E-S", short_name="E2E")
            db.session.add(s)

        lt = LessonType.query.filter_by(name="E2E-LT").first()
        if not lt:
            lt = LessonType(name="E2E-LT")
            db.session.add(lt)

        db.session.flush()

        # ДАННЫЕ ДЛЯ ПРОХОЖДЕНИЯ constraints

        # 2.1 Лимит нагрузки преподавателя — сделаем большим
        wl = WorkloadLimit.query.filter_by(teacher_id=t.id).first()
        if not wl:
            wl = WorkloadLimit(teacher_id=t.id, hours_per_week=100)
            db.session.add(wl)
        else:
            wl.hours_per_week = 100
        
        # 2.2 Доступность преподавателя — весь день, не выходной
        ta = TeacherAvailability.query.filter_by(
            teacher_id=t.id, weekday=date.today().weekday()
        ).first()
        if not ta:
            ta = TeacherAvailability(
                teacher_id=t.id, weekday=date.today().weekday(),
                available_from=None, available_to=None, is_day_off=False
            )
            db.session.add(ta)
        else:
            ta.available_from, ta.available_to, ta.is_day_off = None, None, False

        # 2.3 Учебный план — достаточно часов по предмету
        cur = Curriculum.query.filter_by(group_id=g.id, subject_id=s.id).first()
        if not cur:
            cur = Curriculum(group_id=g.id, subject_id=s.id, total_hours=100)
            db.session.add(cur)
        else:
            cur.total_hours = 100

        # 2.4 На всякий случай — очистим возможные старые пары на сегодня в наших слотах
        Schedule.query.filter(
            Schedule.date == date.today(),
            Schedule.time_slot_id.in_([ts1.id, ts2.id])
        ).delete(synchronize_session=False)

        db.session.commit()
        yield app.test_client()

def test_admin_schedule_crud_e2e(client):
    token = _login_admin(client)

    # lookup
    r = client.get("/api/v1/admin/schedule/lookup")
    assert r.status_code == 200

    # create with pre-check
    g = Group.query.filter_by(code="E2E-G").first()
    t = Teacher.query.filter_by(full_name="E2E-T").first()
    r1 = Room.query.filter_by(number="E2E-101").first()
    s = Subject.query.filter_by(name="E2E-S").first()
    lt = LessonType.query.filter_by(name="E2E-LT").first()
    ts = TimeSlot.query.filter_by(order_no=801).first()

    body = {
        "date": date.today().isoformat(),
        "time_slot_id": ts.id,
        "group_id": g.id,
        "teacher_id": t.id,
        "room_id": r1.id,
        "subject_id": s.id,
        "lesson_type_id": lt.id,
        "is_remote": False,
        "requires_computers": False
    }

    rc = client.post("/api/v1/admin/constraints/check", json=body, headers={"X-CSRF-Token": token})
    assert rc.status_code in (200, 409)  # ok без ошибок или 409 с ошибками — но мы подбираем ок
    js = rc.get_json()
    assert js["ok"] is True and (js["errors"] == [] or js["errors"] is None)

    rcreate = client.post("/api/v1/admin/schedule", json=body, headers={"X-CSRF-Token": token})
    assert rcreate.status_code == 201
    sid = rcreate.get_json()["id"]

    # update (перенос)
    rupdate = client.put(f"/api/v1/admin/schedule/{sid}", json={"time_slot_id": ts.id}, headers={"X-CSRF-Token": token})
    assert rupdate.status_code == 200

    # delete
    rdel = client.delete(f"/api/v1/admin/schedule/{sid}", headers={"X-CSRF-Token": token})
    assert rdel.status_code == 200

    # журнал
    logs = AuditLog.query.order_by(AuditLog.id.desc()).all()
    assert any(l.action=="CREATE" and l.entity=="schedule" for l in logs)
    assert any(l.action=="DELETE" and l.entity=="schedule" for l in logs)
