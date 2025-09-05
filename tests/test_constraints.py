from datetime import date, time
import pytest

from app import create_app
from extensions import db
from models import (
    Group, Teacher, Subject, LessonType,
    Building, RoomType, Room, TimeSlot,
    Schedule, WorkloadLimit, TeacherAvailability, Curriculum
)

# Уникальные значения, но при повторном прогоне берём через get-or-create
GROUP_CODE = "CSTR-G-TEST-01"
TEACHER_NAME = "CSTR Teacher"
SUBJECT_NAME = "CSTR Subject"
LESSONTYPE_NAME = "CSTR Practice"
ROOM_SMALL_NUM = "CSTR-101"
ROOM_BIG_NUM = "CSTR-102"
TS1_ORDER = 91
TS2_ORDER = 92

def _ids():
    g = Group.query.filter_by(code=GROUP_CODE).first()
    t = Teacher.query.filter_by(full_name=TEACHER_NAME).first()
    s = Subject.query.filter_by(name=SUBJECT_NAME).first()
    lt = LessonType.query.filter_by(name=LESSONTYPE_NAME).first()
    r_small = Room.query.filter_by(number=ROOM_SMALL_NUM).first()
    r_big = Room.query.filter_by(number=ROOM_BIG_NUM).first()
    ts1 = TimeSlot.query.filter_by(order_no=TS1_ORDER).first()
    ts2 = TimeSlot.query.filter_by(order_no=TS2_ORDER).first()
    return {
        "group": g.id, "teacher": t.id, "subject": s.id, "lt": lt.id,
        "room_small": r_small.id, "room_big": r_big.id,
        "slot1": ts1.id, "slot2": ts2.id,
    }

def _payload(**kw):
    ids = _ids()
    base = {
        "date": date.today().isoformat(),
        "time_slot_id": ids["slot1"],
        "group_id": ids["group"],
        "subject_id": ids["subject"],
        "lesson_type_id": ids["lt"],
        "teacher_id": ids["teacher"],
        "room_id": ids["room_small"],
        "is_remote": False,
        "requires_computers": True,
        "enforce_building_type": True,
    }
    base.update(kw)
    return base

def _post(client, payload):
    # всегда залогинимся (как в других тестах проекта)
    login_as(client, "t1@example.com", "pass")
    token = csrf(client)
    return client.post(
        "/api/v1/admin/constraints/check",
        json=payload,
        headers={"X-CSRF-Token": token},
    )


def _login_as(client, email, password):
    # пробуем /api/v1/auth/login, если вдруг нет — запасной путь /api/v1/login
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if r.status_code == 404:
        client.post("/api/v1/login", json={"email": email, "password": password})

def _csrf(client):
    r = client.get("/api/v1/csrf")
    js = r.get_json() or {}
    return js.get("csrf", "")

# ... ниже по файлу оставь всё как есть, но в _post используй эти хелперы:
def _post(client, payload):
    _login_as(client, "t1@example.com", "pass")
    token = _csrf(client)
    return client.post(
        "/api/v1/admin/constraints/check",
        json=payload,
        headers={"X-CSRF-Token": token},
    )

@pytest.fixture()
def client():
    app = create_app("dev")
    # важно: не рассчитываем на смену URI после init_app,
    # работаем с тем, что есть (в dev БД), значит избегаем дублей
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()

        # get-or-create блоки на всё, что может быть уникальным
        b_spo = Building.query.filter_by(name="СПО корпус (CSTR)").first()
        if not b_spo:
            b_spo = Building(name="СПО корпус (CSTR)", address="ул. 1", type="СПО")
            db.session.add(b_spo)

        b_vo = Building.query.filter_by(name="ВО корпус (CSTR)").first()
        if not b_vo:
            b_vo = Building(name="ВО корпус (CSTR)", address="ул. 2", type="ВО")
            db.session.add(b_vo)

        rt_pc = RoomType.query.filter_by(name="ПК класс (CSTR)").first()
        if not rt_pc:
            rt_pc = RoomType(name="ПК класс (CSTR)", requires_computers=True)
            db.session.add(rt_pc)

        rt_norm = RoomType.query.filter_by(name="Обычный (CSTR)").first()
        if not rt_norm:
            rt_norm = RoomType(name="Обычный (CSTR)", requires_computers=False)
            db.session.add(rt_norm)

        db.session.flush()

        r_small = Room.query.filter_by(number=ROOM_SMALL_NUM).first()
        if not r_small:
            r_small = Room(building_id=b_spo.id, number=ROOM_SMALL_NUM,
                           capacity=20, room_type_id=rt_pc.id, computers_count=10)
            db.session.add(r_small)

        r_big = Room.query.filter_by(number=ROOM_BIG_NUM).first()
        if not r_big:
            r_big = Room(building_id=b_spo.id, number=ROOM_BIG_NUM,
                         capacity=40, room_type_id=rt_pc.id, computers_count=40)
            db.session.add(r_big)

        ts1 = TimeSlot.query.filter_by(order_no=TS1_ORDER).first()
        if not ts1:
            ts1 = TimeSlot(order_no=TS1_ORDER, start_time=time(8, 30), end_time=time(10, 0))
            db.session.add(ts1)

        ts2 = TimeSlot.query.filter_by(order_no=TS2_ORDER).first()
        if not ts2:
            ts2 = TimeSlot(order_no=TS2_ORDER, start_time=time(10, 10), end_time=time(11, 40))
            db.session.add(ts2)

        t = Teacher.query.filter_by(full_name=TEACHER_NAME).first()
        if not t:
            t = Teacher(full_name=TEACHER_NAME, short_name="CSTR")
            db.session.add(t)

        g = Group.query.filter_by(code=GROUP_CODE).first()
        if not g:
            g = Group(code=GROUP_CODE, name="CSTR Group", students_count=25, education_level="СПО")
            db.session.add(g)

        s = Subject.query.filter_by(name=SUBJECT_NAME).first()
        if not s:
            s = Subject(name=SUBJECT_NAME, short_name="CS")
            db.session.add(s)

        lt = LessonType.query.filter_by(name=LESSONTYPE_NAME).first()
        if not lt:
            lt = LessonType(name=LESSONTYPE_NAME)
            db.session.add(lt)

        db.session.flush()

        # ограничения (тоже get-or-create по уникальным ключам)
        wl = WorkloadLimit.query.filter_by(teacher_id=t.id).first()
        if not wl:
            wl = WorkloadLimit(teacher_id=t.id, hours_per_week=1)
            db.session.add(wl)
        else:
            wl.hours_per_week = 1

        ta = TeacherAvailability.query.filter_by(
            teacher_id=t.id, weekday=date.today().weekday()
        ).first()
        if not ta:
            ta = TeacherAvailability(
                teacher_id=t.id, weekday=date.today().weekday(),
                available_from=time(12, 0), available_to=time(14, 0), is_day_off=False
            )
            db.session.add(ta)
        else:
            ta.available_from, ta.available_to, ta.is_day_off = time(12, 0), time(14, 0), False

        cur = Curriculum.query.filter_by(group_id=g.id, subject_id=s.id).first()
        if not cur:
            cur = Curriculum(group_id=g.id, subject_id=s.id, total_hours=1)
            db.session.add(cur)
        else:
            cur.total_hours = 1

        # чистим потенциальные старые пары в наши тестовые слоты/дату
        Schedule.query.filter(
            Schedule.date == date.today(),
            Schedule.time_slot_id.in_([ts1.id, ts2.id])
        ).delete(synchronize_session=False)

        db.session.commit()
        yield app.test_client()

def test_room_capacity_exceeded(client):
    r = _post(client, _payload(room_id=_ids()["room_small"]))
    js = r.get_json()
    assert r.status_code == 409
    assert "ROOM_CAPACITY_EXCEEDED" in [e["code"] for e in js["errors"]]

def test_room_computers_not_enough(client):
    r = _post(client, _payload(room_id=_ids()["room_small"], requires_computers=True))
    js = r.get_json()
    assert "ROOM_COMPUTERS_NOT_ENOUGH" in [e["code"] for e in js["errors"]]

def test_remote_ignores_room_checks(client):
    r = _post(client, _payload(is_remote=True, room_id=None))
    js = r.get_json()
    codes = [e["code"] for e in js["errors"]]
    assert "ROOM_CAPACITY_EXCEEDED" not in codes
    assert "ROOM_COMPUTERS_NOT_ENOUGH" not in codes

def test_teacher_group_room_busy(client):
    ids = _ids()
    db.session.add(Schedule(
        date=date.today(), time_slot_id=ids["slot1"],
        group_id=ids["group"], subject_id=ids["subject"],
        lesson_type_id=ids["lt"], teacher_id=ids["teacher"],
        room_id=ids["room_small"]
    ))
    db.session.commit()
    r = _post(client, _payload())
    js = r.get_json()
    codes = [e["code"] for e in js["errors"]]
    assert "TEACHER_BUSY" in codes
    assert "GROUP_BUSY" in codes
    assert "ROOM_BUSY" in codes

def test_teacher_limit_exceeded(client):
    ids = _ids()
    Schedule.query.delete()
    db.session.add(Schedule(
        date=date.today(), time_slot_id=ids["slot2"],
        group_id=ids["group"], subject_id=ids["subject"],
        lesson_type_id=ids["lt"], teacher_id=ids["teacher"],
        room_id=ids["room_big"]
    ))
    db.session.commit()
    r = _post(client, _payload(time_slot_id=ids["slot1"], room_id=ids["room_big"]))
    js = r.get_json()
    assert "TEACHER_LIMIT_EXCEEDED" in [e["code"] for e in js["errors"]]

def test_teacher_not_available(client):
    r = _post(client, _payload())
    js = r.get_json()
    assert "TEACHER_NOT_AVAILABLE" in [e["code"] for e in js["errors"]]

def test_curriculum_hours_exceeded(client):
    ids = _ids()
    db.session.add(Schedule(
        date=date.today(), time_slot_id=ids["slot2"],
        group_id=ids["group"], subject_id=ids["subject"],
        lesson_type_id=ids["lt"], teacher_id=ids["teacher"],
        room_id=ids["room_big"]
    ))
    db.session.commit()
    r = _post(client, _payload(time_slot_id=ids["slot1"], room_id=ids["room_big"]))
    js = r.get_json()
    assert "CURRICULUM_HOURS_EXCEEDED" in [e["code"] for e in js["errors"]]

def test_invalid_building(client):
    ids = _ids()
    b_vo = Building.query.filter_by(type="ВО").first()
    room_big = Room.query.filter_by(number=ROOM_BIG_NUM).first()
    room_big.building_id = b_vo.id
    db.session.commit()
    r = _post(client, _payload(room_id=ids["room_big"]))
    js = r.get_json()
    assert "INVALID_BUILDING" in [e["code"] for e in js["errors"]]

def test_ok_case(client):
    ids = _ids()
    wl = WorkloadLimit.query.filter_by(teacher_id=ids["teacher"]).first()
    wl.hours_per_week = 100
    TeacherAvailability.query.delete()
    db.session.add(TeacherAvailability(
        teacher_id=ids["teacher"], weekday=date.today().weekday(),
        available_from=None, available_to=None, is_day_off=False
    ))
    cur = Curriculum.query.filter_by(group_id=ids["group"], subject_id=ids["subject"]).first()
    cur.total_hours = 999
    Schedule.query.delete()
    db.session.commit()

    r = _post(client, _payload(room_id=ids["room_big"]))
    js = r.get_json()
    assert js["ok"] is True
    assert js["errors"] == []
