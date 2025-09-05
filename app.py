from flask import Flask
from dotenv import load_dotenv
import os

from extensions import db, migrate, login_manager, cache
from config import DevelopmentConfig, ProductionConfig, TestingConfig

def create_app():
    load_dotenv()  # load .env if present
    env = os.getenv("FLASK_ENV", "development")
    config_cls = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }.get(env, DevelopmentConfig)

    app = Flask(__name__, instance_relative_config=True, template_folder="templates", static_folder="static")
    app.config.from_object(config_cls)
    # Ensure instance folder exists for sqlite default path
    app.instance_path  # triggers creation

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)

    # Register blueprints
    from blueprints.core import bp as core_bp
    from blueprints.search import bp as search_bp
    from blueprints.schedule import bp as schedule_bp
    from blueprints.auth import bp as auth_bp
    from blueprints.directory import bp as directory_bp
    from blueprints.planning import bp as planning_bp
    from blueprints.constraints import bp as constraints_bp
    from blueprints.homework import bp as homework_bp
    from blueprints.teacher import bp as teacher_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.reports import bp as reports_bp
    from blueprints.import_export import bp as import_export_bp
    from blueprints.api import bp as api_bp

    app.register_blueprint(core_bp)  # url_prefix set inside
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
    app.register_blueprint(import_export_bp, url_prefix="/import_export")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Models import to register with SQLAlchemy metadata
    from models import *  # noqa: F401,F403

    return app

# For flask CLI discovery: `flask --app app.py run`
app = create_app()
