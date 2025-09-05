from __future__ import annotations
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import User

@pytest.fixture()
def client_app():
    app = create_app("dev")
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        AUTH_RL_MAX=3, AUTH_RL_WINDOW=60,  # агрессивный лимит для теста
        WTF_CSRF_ENABLED=False,  # мы используем свой CSRF
    )
    with app.app_context():
        db.create_all()
        db.session.add_all([
            User(email="admin@example.com", password_hash=generate_password_hash("adminpass"), role="ADMIN", is_active=True),
            User(email="teacher@example.com", password_hash=generate_password_hash("teachpass"), role="TEACHER", is_active=True),
        ])
        db.session.commit()
        yield app
        db.drop_all()

@pytest.fixture()
def client(client_app):
    return client_app.test_client()

def _get_csrf(client):
    r = client.get("/api/v1/auth/csrf")
    assert r.status_code == 200
    return r.get_json()["csrf_token"]

def test_unauthorized_401(client):
    r = client.get("/auth/ping-admin")
    assert r.status_code == 401  # unauthorized

def test_forbidden_403(client):
    csrf = _get_csrf(client)
    # логин как TEACHER
    r = client.post("/api/v1/auth/login", json={"email":"teacher@example.com","password":"teachpass"},
                    headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    # доступ к admin-эндпоинту запрещён
    r2 = client.get("/auth/ping-admin")
    assert r2.status_code == 403

def test_login_success_and_ping_teacher(client):
    csrf = _get_csrf(client)
    r = client.post("/api/v1/auth/login", json={"email":"admin@example.com","password":"adminpass"},
                    headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    js = r.get_json()
    assert js["ok"] is True and js["user"]["role"] == "ADMIN"

    # admin допускается к teacher-ресурсу
    r2 = client.get("/auth/ping-teacher")
    assert r2.status_code == 200
    assert r2.get_json()["role"] == "ADMIN"

def test_rate_limit_login(client):
    csrf = _get_csrf(client)
    for _ in range(3):  # AUTH_RL_MAX
        r = client.post("/api/v1/auth/login", json={"email":"x@example.com","password":"wrong"},
                        headers={"X-CSRF-Token": csrf})
        # первые 2-3 могут быть 401, важно, что следующий — 429
    r2 = client.post("/api/v1/auth/login", json={"email":"x@example.com","password":"wrong"},
                     headers={"X-CSRF-Token": csrf})
    assert r2.status_code == 429

def test_logout(client):
    csrf = _get_csrf(client)
    r = client.post("/api/v1/auth/login", json={"email":"teacher@example.com","password":"teachpass"},
                    headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    # logout
    csrf2 = _get_csrf(client)  # новый токен (не обязательно, но корректно)
    r2 = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf2})
    assert r2.status_code == 200
    # теперь защищённый ресурс снова 401
    r3 = client.get("/auth/ping-teacher")
    assert r3.status_code == 401
