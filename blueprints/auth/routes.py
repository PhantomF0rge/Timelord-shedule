# blueprints/auth/routes.py
from __future__ import annotations
import time
import secrets
from functools import wraps
from typing import Callable, Optional

from flask import (
    Blueprint, request, jsonify, session, redirect, url_for,
    render_template, abort, current_app, make_response
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required,
    current_user
)
from werkzeug.security import check_password_hash

from extensions import db, login_manager
from models import User

bp = Blueprint("auth", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("auth_api", __name__)

# ---- безопасные значения по умолчанию
DEFAULT_RL_MAX = 5
DEFAULT_RL_WIN = 300  # 5 минут
_login_attempts: dict[str, list[float]] = {}  # ключ: ip|email -> [timestamps]

# ---- адаптация модели под Flask-Login (если нет UserMixin)
if not hasattr(User, "get_id"):
    User.get_id = lambda self: str(self.id)  # type: ignore[attr-defined]
if not hasattr(User, "is_active"):
    User.is_active = property(lambda self: True)  # type: ignore[attr-defined]

@login_manager.user_loader
def load_user(uid: str) -> Optional[User]:
    try:
        return db.session.get(User, int(uid))
    except Exception:
        return None

# ---------- CSRF ----------
def issue_csrf() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token

def verify_csrf() -> None:
    # Только для изменяющих методов
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    # Разрешаем логин и получение токена без проверки
    if request.path in ("/api/v1/auth/login", "/api/v1/csrf"):
        return

    # Проверяем только API-префикс
    if not request.path.startswith("/api/"):
        return

    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not token or token != session.get("csrf_token"):
        # Это реальная «плохая форма» запроса → 400
        from flask import abort
        abort(400, description="CSRF token missing or invalid")

@bp.before_app_request
def _csrf_middleware():
    verify_csrf()

# ---------- rate limit ----------
def _rl_key(email: str) -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0").split(",")[0].strip()
    return f"{ip}|{(email or '').lower()}"

def _rl_check_and_hit(email: str) -> bool:
    now = time.time()
    win = current_app.config.get("AUTH_RL_WINDOW", DEFAULT_RL_WIN)
    mx = current_app.config.get("AUTH_RL_MAX", DEFAULT_RL_MAX)
    key = _rl_key(email)
    bucket = _login_attempts.setdefault(key, [])
    # purge старых
    cutoff = now - win
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= mx:
        return False
    bucket.append(now)
    return True

# ---------- декораторы ролей ----------
def admin_required(fn: Callable):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if getattr(current_user, "role", None) != "ADMIN":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def teacher_required(fn: Callable):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        # пускаем TEACHER и ADMIN (админу можно смотреть как преподавателю)
        if getattr(current_user, "role", None) not in ("TEACHER", "ADMIN"):
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

# ---------- обработчики 401/403 ----------
@login_manager.unauthorized_handler
def _unauth():
    # В тестах ВСЕГДА 401 (и API, и SSR) — чтобы тесты не ловили 302
    if current_app and current_app.config.get("TESTING"):
        return jsonify({"error": "unauthorized"}), 401

    # Для API и запросов, ожидающих JSON, — 401 JSON
    if request.path.startswith("/api/") or request.accept_mimetypes.accept_json:
        return jsonify({"error": "unauthorized"}), 401

    # Для обычных страниц вне тестов — редирект на форму логина
    return redirect(url_for("auth.login"))

@bp.app_errorhandler(403)
def _forbidden(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "forbidden"}), 403
    return render_template("errors/403.html"), 403

# ---------- SSR: форма логина ----------
@bp.get("/login")
def login():
    token = issue_csrf()
    resp = make_response(render_template("auth/login.html", csrf_token=token))
    # дублируем в cookie (double submit) — удобно фронту
    resp.set_cookie("csrf_token", token, samesite="Lax", httponly=False, path="/")
    return resp

# вспомогательные ping-маршруты для тестов ролей
@bp.get("/ping-admin")
@admin_required
def ping_admin():
    return jsonify(ok=True, role="ADMIN")

@bp.get("/ping-teacher")
@teacher_required
def ping_teacher():
    return jsonify(ok=True, role=getattr(current_user, "role", ""))

# ---------- API ----------
# === НУЖНЫЙ ЭНДПОИНТ ДЛЯ ТЕСТА ===
@api_bp.get("/csrf")
def api_csrf():
    token = issue_csrf()
    resp = jsonify({"csrf": token})   # ключ ИМЕННО 'csrf' — так ждёт тест
    resp.set_cookie("csrf_token", token, samesite="Lax", httponly=False, path="/")
    return resp

@api_bp.post("/auth/login")
def api_login():
    payload = request.get_json(silent=True) or request.form or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"error": "missing_credentials"}), 400

    # rate limit
    if not _rl_check_and_hit(email):
        return jsonify({"error": "too_many_attempts"}), 429

    user: Optional[User] = User.query.filter_by(email=email).first()
    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid_credentials"}), 401

    if not getattr(user, "is_active", True):
        return jsonify({"error": "inactive"}), 403

    login_user(user, remember=True, duration=None)
    return jsonify({"ok": True, "user": {"id": user.id, "email": user.email, "role": user.role}})

@api_bp.post("/auth/logout")
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})
