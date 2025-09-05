from flask import Flask
from config import Config
from extensions import db, migrate, login_manager

# Import blueprints
from blueprints.core import bp as core_bp
from blueprints.auth import bp as auth_bp
from blueprints.search import bp as search_bp
from blueprints.schedule import bp as schedule_bp
from blueprints.directory import bp as directory_bp
from blueprints.planning import bp as planning_bp
from blueprints.constraints import bp as constraints_bp
from blueprints.homework import bp as homework_bp
from blueprints.teacher import bp as teacher_bp
from blueprints.admin import bp as admin_bp
from blueprints.reports import bp as reports_bp
from blueprints.import_export import bp as import_export_bp
from blueprints.api import bp as api_bp

from models import *  # noqa

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    # Регистрация обязательных блюпринтов
    from blueprints.core import bp as core_bp
    app.register_blueprint(core_bp)

    from blueprints.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Опциональные блюпринты — регистрируем, только если есть
    def _try_register(import_path, attr, prefix=None):
        try:
            mod = __import__(import_path, fromlist=[attr])
            bp = getattr(mod, attr)
            app.register_blueprint(bp, url_prefix=prefix)
        except Exception:
            pass

    _try_register("blueprints.admin", "bp", "/admin")
    _try_register("blueprints.planning", "bp", "/planning")
    _try_register("blueprints.search", "bp", "/search")
    _try_register("blueprints.auth", "bp", "/auth")
    _try_register("blueprints.schedule", "bp", "/schedule")
    _try_register("blueprints.directory", "bp", "/directory")
    _try_register("blueprints.teacher", "bp", "/teacher")
    _try_register("blueprints.homework", "bp", "/homework")
    _try_register("blueprints.reports", "bp", "/reports")
    _try_register("blueprints.import_export", "bp", "/import-export")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
