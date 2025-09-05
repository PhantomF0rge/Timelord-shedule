from __future__ import annotations
import pytest
from app import create_app
from extensions import db

@pytest.fixture()
def client():
    app = create_app("dev")
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.create_all()
        with app.test_client() as c:
            yield c
        db.session.remove()
        db.drop_all()

def test_group_crud_and_uniqueness(client):
    # create
    r = client.post("/directory/api/groups", json={"code":"ИТ-101","name":"Инфо","students_count":25,"education_level":"СПО"})
    assert r.status_code == 201
    gid = r.get_json()["id"]

    # get
    r = client.get(f"/directory/api/groups/{gid}")
    assert r.status_code == 200
    assert r.get_json()["code"] == "ИТ-101"

    # unique code
    r = client.post("/directory/api/groups", json={"code":"ИТ-101","name":"dup","students_count":10,"education_level":"СПО"})
    assert r.status_code in (400, 409)  # ожидаем конфликт

    # update
    r = client.put(f"/directory/api/groups/{gid}", json={"code":"ИТ-101","name":"Информатика","students_count":30,"education_level":"СПО"})
    assert r.status_code == 200

    # list + search
    r = client.get("/directory/api/groups?q=ИТ-101")
    assert r.status_code == 200
    data = r.get_json()
    assert data["meta"]["total"] >= 1

    # delete
    r = client.delete(f"/directory/api/groups/{gid}")
    assert r.status_code == 204

def test_room_uniqueness_building_number(client):
    # создать корпус и тип
    client.post("/directory/api/buildings", json={"name":"СПО","address":"x","type":"СПО"})
    rt = client.post("/directory/api/room-types", json={"name":"Обычная","requires_computers":False,"sports":False})
    room_type_id = rt.get_json()["id"]

    # ok
    r1 = client.post("/directory/api/rooms", json={"building_id":1,"number":"101","capacity":30,"room_type_id":room_type_id,"computers_count":0})
    assert r1.status_code == 201
    # конфликт по (building_id, number)
    r2 = client.post("/directory/api/rooms", json={"building_id":1,"number":"101","capacity":32,"room_type_id":room_type_id,"computers_count":0})
    assert r2.status_code in (400,409)

    # но в другом корпусе — можно
    client.post("/directory/api/buildings", json={"name":"ВО","address":"y","type":"ВО"})
    r3 = client.post("/directory/api/rooms", json={"building_id":2,"number":"101","capacity":50,"room_type_id":room_type_id,"computers_count":0})
    assert r3.status_code == 201

def test_timeslot_validation(client):
    # end_time must be > start_time
    bad = client.post("/directory/api/time-slots", json={"order_no":1,"start_time":"10:00","end_time":"09:00"})
    assert bad.status_code == 400 or bad.status_code == 422

    ok = client.post("/directory/api/time-slots", json={"order_no":1,"start_time":"08:30","end_time":"10:00"})
    assert ok.status_code == 201

def test_pagination_subjects(client):
    for i in range(30):
        client.post("/directory/api/subjects", json={"name":f"Sub{i}"})
    r = client.get("/directory/api/subjects?page=2&per_page=10")
    assert r.status_code == 200
    data = r.get_json()
    assert data["meta"]["page"] == 2
    assert len(data["items"]) == 10
