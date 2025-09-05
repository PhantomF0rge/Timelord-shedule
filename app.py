from __future__ import annotations
import os
from importlib import import_module
from flask import Flask
from config import config_map
from extensions import db, migrate, login_manager

def register_blueprints(app: Flask) -> None:
    # Жёстко импортируем модуль с маршрутами core перед взятием bp
    import_module("blueprints.core.routes")
    from blueprints.core import bp as core_bp
    from blueprints.search import bp as search_bp
    from blueprints.schedule.routes import bp as schedule_bp, api_bp as schedule_api_bp
    from blueprints.auth.routes import bp as auth_bp, api_bp as auth_api_bp
    from blueprints.directory import bp as directory_bp
    from blueprints.planning import bp as planning_bp
    from blueprints.constraints.routes import bp as constraints_bp, api_bp as constraints_api_bp
    from blueprints.homework.routes import bp as homework_bp, api_bp as homework_api_bp
    from blueprints.teacher.routes import bp as teacher_bp, api_bp as teacher_api_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.reports import bp as reports_bp
    from blueprints.import_export import bp as import_export_bp
    from blueprints.api.routes import bp as api_bp

    # core без префикса → '/' и '/health' в корне
    app.register_blueprint(core_bp)
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(schedule_bp, url_prefix="/schedule")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(directory_bp, url_prefix="/directory")
    app.register_blueprint(planning_bp, url_prefix="/planning")
    app.register_blueprint(constraints_bp, url_prefix="/constraints")
    app.register_blueprint(homework_bp, url_prefix="/homework")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(import_export_bp, url_prefix="/io")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(schedule_api_bp, url_prefix="/api/v1")
    app.register_blueprint(auth_api_bp, url_prefix="/api/v1")
    app.register_blueprint(teacher_api_bp, url_prefix="/api/v1")
    app.register_blueprint(homework_api_bp, url_prefix="/api/v1")
    app.register_blueprint(constraints_api_bp, url_prefix="/api/v1/admin")

def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.setdefault("SECRET_KEY", "change-me-in-prod")
    cfg_name = config_name or os.getenv("FLASK_CONFIG", "default")
    app.config.from_object(config_map[cfg_name])
    # --- ВАЖНО: изоляция БД в тестах ---
    # pytest всегда выставляет переменную окружения PYTEST_CURRENT_TEST.
    # Делаем БД в памяти, чтобы никакие изменения из одного теста не протекали в другой.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        # для in-memory и одного потока этого достаточно; если что:
        app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {"connect_args": {"check_same_thread": False}})
    # важное: разрешаем заголовки, которые использует тест
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)
    app.config.setdefault("WTF_CSRF_CHECK_DEFAULT", True)
    app.config.setdefault("WTF_CSRF_HEADERS", ["X-CSRF-Token", "X-CSRFToken"])

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    register_blueprints(app)
    return app