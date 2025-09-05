# tests/test_import_export.py
from io import BytesIO
from datetime import time
import json
import pytest
from app import create_app
from extensions import db
from werkzeug.security import generate_password_hash
from models import (
    User, Group, Teacher, Subject, LessonType,
    Building, RoomType, Room, Curriculum, TimeSlot
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
                    json={"email":"admin@example.com","password":"pass"},
                    headers={"X-CSRF-Token": t})
    assert r.status_code == 200
    return _csrf(client)

@pytest.fixture()
def client():
    app = create_app("dev")
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()
        # базовые сущности для rooms/curriculum
        b = Building.query.filter_by(name="IMP-B").first()
        if not b:
            b = Building(name="IMP-B", address="x", type="СПО"); db.session.add(b); db.session.flush()
        rt = RoomType.query.filter_by(name="IMP-RT").first()
        if not rt:
            rt = RoomType(name="IMP-RT", requires_computers=False); db.session.add(rt); db.session.flush()
        if not Room.query.filter_by(building_id=b.id, number="301").first():
            db.session.add(Room(building_id=b.id, number="301", capacity=20, room_type_id=rt.id, computers_count=0))
        if not Subject.query.filter_by(name="IMP-SUBJ").first():
            db.session.add(Subject(name="IMP-SUBJ", short_name="IS"))
        if not Group.query.filter_by(code="IMP-G").first():
            db.session.add(Group(code="IMP-G", name="Imp Group", students_count=20, education_level="СПО"))
        if not LessonType.query.filter_by(name="IMP-LT").first():
            db.session.add(LessonType(name="IMP-LT"))
        if not TimeSlot.query.filter_by(order_no=990).first():
            db.session.add(TimeSlot(order_no=990, start_time=time(8,30), end_time=time(10,0)))
        db.session.commit()
        yield app.test_client()

def _file(data: str, name="file.csv"):
    return BytesIO(data.encode("utf-8"))

def test_preview_detects_mapping_groups(client):
    token = _login_admin(client)
    data = "code,name,students_count,education_level\nA1,Alpha,10,СПО\n"
    rv = client.post("/api/v1/admin/import/preview?entity=groups",
                     data={"file": ( _file(data), "groups.csv") },
                     headers={"X-CSRF-Token": token})
    assert rv.status_code == 200
    js = rv.get_json()
    assert js["ok"] and "detected_mapping" in js
    assert js["detected_mapping"].get("code") == "code"

def test_dry_run_duplicates_and_errors(client):
    token = _login_admin(client)
    # второй ряд — дубликат кода
    data = "code,name,students_count,education_level\nG1,One,20,СПО\nG1,Two,25,СПО\n"
    mapping = {"code":"code","name":"name","students_count":"students_count","education_level":"education_level"}
    rv = client.post("/api/v1/admin/import/validate?entity=groups",
                     data={"file": (_file(data),"g.csv"), "mapping": json.dumps(mapping)},
                     headers={"X-CSRF-Token": token})
    assert rv.status_code == 200
    js = rv.get_json()
    assert js["ok"] is False
    assert len(js["duplicates"]) == 1
    # students_count как строка "xx" вызовет INVALID_INT
    data2 = "code,name,students_count,education_level\nG2,Two,xx,СПО\n"
    rv2 = client.post("/api/v1/admin/import/validate?entity=groups",
                      data={"file": (_file(data2),"g2.csv"), "mapping": json.dumps(mapping)},
                      headers={"X-CSRF-Token": token})
    assert rv2.status_code == 200
    assert any(e["code"]=="INVALID_INT" for e in rv2.get_json()["row_errors"])

def test_commit_atomic_success_and_rollback(client):
    token = _login_admin(client)
    # OK + BAD (неизвестное здание для rooms) => rollback всего батча
    data_bad = "building,room_type,number,capacity,computers\nUNKNOWN,IMP-RT,501,30,0\n"
    mapping_rooms = {"building_name":"building","room_type_name":"room_type","number":"number","capacity":"capacity","computers_count":"computers"}
    rv1 = client.post("/api/v1/admin/import/commit?entity=rooms",
                      data={"file": (_file(data_bad), "rooms_bad.csv"), "mapping": json.dumps(mapping_rooms)},
                      headers={"X-CSRF-Token": token})
    assert rv1.status_code == 422

    # groups — успех
    gdata = "code,name,students_count,education_level\nX1,X,20,СПО\nX2,Y,25,СПО\n"
    gmap = {"code":"code","name":"name","students_count":"students_count","education_level":"education_level"}
    rv2 = client.post("/api/v1/admin/import/commit?entity=groups",
                      data={"file": (_file(gdata), "g.csv"), "mapping": json.dumps(gmap)},
                      headers={"X-CSRF-Token": token})
    assert rv2.status_code == 200
    assert rv2.get_json()["committed"] == 2
    # повторная попытка с теми же кодами — дубликаты => 422
    rv3 = client.post("/api/v1/admin/import/commit?entity=groups",
                      data={"file": (_file(gdata), "g2.csv"), "mapping": json.dumps(gmap)},
                      headers={"X-CSRF-Token": token})
    assert rv3.status_code == 422

def test_curriculum_import(client):
    token = _login_admin(client)
    data = "group,subject,hours\nIMP-G,IMP-SUBJ,36\n"
    mapping = {"group_code":"group","subject_name":"subject","total_hours":"hours"}
    rv = client.post("/api/v1/admin/import/validate?entity=curriculum",
                     data={"file": (_file(data), "cur.csv"), "mapping": json.dumps(mapping)},
                     headers={"X-CSRF-Token": token})
    assert rv.status_code == 200
    assert rv.get_json()["ok"] is True
    rc = client.post("/api/v1/admin/import/commit?entity=curriculum",
                     data={"file": (_file(data), "cur.csv"), "mapping": json.dumps(mapping)},
                     headers={"X-CSRF-Token": token})
    assert rc.status_code == 200
    # повторно — дубликат по (group,subject)
    rc2 = client.post("/api/v1/admin/import/commit?entity=curriculum",
                      data={"file": (_file(data), "cur2.csv"), "mapping": json.dumps(mapping)},
                      headers={"X-CSRF-Token": token})
    assert rc2.status_code == 422
