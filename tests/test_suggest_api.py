# tests/test_suggest_api.py
from __future__ import annotations
import time
import types
import pytest
from app import create_app
from extensions import db
from models import Group, Teacher, Subject

@pytest.fixture()
def client():
    app = create_app("dev")
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"check_same_thread": False}},
    )
    with app.app_context():
        # ✅ чистая схема на каждый тест
        db.drop_all()
        db.create_all()

        # demo data
        db.session.add_all([
            Group(code="ИТ-101", name="Информатика 1", students_count=25, education_level="СПО"),
            Group(code="ИТ-102", name="Информатика 2", students_count=26, education_level="СПО"),
            Group(code="ФК-201", name="Физкультура",    students_count=22, education_level="СПО"),
        ])
        db.session.add_all([
            Teacher(full_name="Иванов Иван Иванович", short_name="Иванов"),
            Teacher(full_name="Петров Пётр Петрович", short_name="Петров"),
        ])
        db.session.add_all([
            Subject(name="Информатика",       short_name="Инф."),
            Subject(name="Программирование",  short_name="Прог."),
        ])
        db.session.commit()

        with app.test_client() as c:
            yield c

        # ✅ аккуратный teardown
        db.session.remove()
        db.drop_all()

def test_suggest_groups_prefix_first(client):
    r = client.get("/api/v1/suggest?q=ИТ&type=group&limit=5")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert items
    assert items[0]["type"] == "group"
    assert items[0]["label"].startswith("ИТ")  # префикс приоритетнее

def test_suggest_teachers(client):
    r = client.get("/api/v1/suggest?q=Иван&type=teacher&limit=5")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any("Иванов" in it["label"] for it in items)

def test_suggest_subjects(client):
    r = client.get("/api/v1/suggest?q=Прог&type=subject&limit=5")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any("Программирование" in it["label"] for it in items)

def test_suggest_limit(client):
    r = client.get("/api/v1/suggest?q=И&type=group&limit=1")
    assert r.status_code == 200
    assert len(r.get_json()["items"]) == 1

def test_suggest_invalid_type(client):
    r = client.get("/api/v1/suggest?q=И&type=oopsy")
    assert r.status_code == 400

def test_suggest_speed_with_mock(client, monkeypatch):
    # Мокаем сервис, чтобы имитировать тяжёлый поиск и замерить оверхед эндпоинта
    from blueprints.search import services as svc

    def slow_suggest(**kwargs):
        time.sleep(0.01)  # 10мс «тяжёлой» работы БД
        return [{"type":"group","id":1,"label":"ИТ-101","hint":"Информатика"}]

    monkeypatch.setattr(svc, "suggest", slow_suggest)
    t0 = time.perf_counter()
    r = client.get("/api/v1/suggest?q=ИТ&type=group")
    dt = (time.perf_counter() - t0)
    assert r.status_code == 200
    assert dt < 0.08  # сам эндпоинт добавляет <~70мс к «работе БД»
