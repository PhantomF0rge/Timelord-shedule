# tests/test_planning.py
from datetime import date, timedelta, time
import pytest
from app import create_app
from extensions import db
from werkzeug.security import generate_password_hash
from models import User, TimeSlot

def _csrf(client):
    r = client.get("/api/v1/csrf")
    return (r.get_json() or {}).get("csrf", "")

def _login_admin(client):
    # ensure admin
    if not User.query.filter_by(email="admin@example.com").first():
        db.session.add(User(
            email="admin@example.com",
            role="ADMIN",
            password_hash=generate_password_hash("pass"),
        ))
        db.session.commit()

    # 1) берём CSRF и логинимся с ним
    t1 = _csrf(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "pass"},
        headers={"X-CSRF-Token": t1},
    )
    assert r.status_code == 200, r.get_json()

    # 2) после логина берём свежий CSRF для дальнейших POST
    return _csrf(client)

@pytest.fixture()
def client():
    app = create_app("dev")
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()
        if not TimeSlot.query.first():
            db.session.add_all([
                TimeSlot(order_no=1, start_time=time(8, 30), end_time=time(10, 0)),
                TimeSlot(order_no=2, start_time=time(10, 10), end_time=time(11, 40)),
            ])
            db.session.commit()
        yield app.test_client()

def test_generate_and_commit(client):
    token = _login_admin(client)

    body = {
        "date_from": date.today().isoformat(),
        "date_to": (date.today() + timedelta(days=1)).isoformat(),
        "honor_holidays": True,
    }

    r = client.post(
        "/api/v1/admin/planning/generate",
        json=body,
        headers={"X-CSRF-Token": token},
    )
    assert r.status_code == 200, r.get_json()
    pid = r.get_json()["preview_id"]

    r2 = client.get(f"/api/v1/admin/planning/preview?id={pid}")
    assert r2.status_code == 200, r2.get_json()

    r3 = client.post(
        "/api/v1/admin/planning/commit",
        json={"preview_id": pid},
        headers={"X-CSRF-Token": token},
    )
    # Ок, если всё закоммитили (200) или нашлись конфликты (409).
    # Если у тебя commit пока возвращает 400 при пустом списке — добавь 400 сюда, либо сделай 200 при пустом коммите.
    assert r3.status_code in (200, 409)
