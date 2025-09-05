from flask import Flask
from config import Config
from extensions import db, migrate, login_manager

def register_blueprints(app: Flask) -> None:
    # core
    from blueprints.core import bp as core_bp
    app.register_blueprint(core_bp)

    # остальные блюпринты со своими префиксами
    from blueprints.search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix="/search")

    from blueprints.schedule import bp as schedule_bp
    app.register_blueprint(schedule_bp, url_prefix="/schedule")

    from blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from blueprints.directory import bp as directory_bp
    app.register_blueprint(directory_bp, url_prefix="/directory")

    from blueprints.planning import bp as planning_bp
    app.register_blueprint(planning_bp, url_prefix="/planning")

    from blueprints.constraints import bp as constraints_bp
    app.register_blueprint(constraints_bp, url_prefix="/constraints")

    from blueprints.homework import bp as homework_bp
    app.register_blueprint(homework_bp, url_prefix="/homework")

    from blueprints.teacher import bp as teacher_bp
    app.register_blueprint(teacher_bp, url_prefix="/teacher")

    from blueprints.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from blueprints.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix="/reports")

    from blueprints.import_export import bp as import_export_bp
    app.register_blueprint(import_export_bp, url_prefix="/import-export")

    from blueprints.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api/v1")

def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    register_blueprints(app)
    # заглушка загрузчика пользователя (иначе Flask-Login роняет шаблоны)
    @login_manager.user_loader
    def load_user(user_id: str):
        return None
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

from extensions import login_manager

@login_manager.user_loader
def load_user(user_id: str):
    # На этапе каркаса пользователей ещё нет — возвращаем None (аноним)
    return None