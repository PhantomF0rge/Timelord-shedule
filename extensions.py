from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# ORM
db = SQLAlchemy()

# Alembic/Flask-Migrate
migrate = Migrate()

# Auth
login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message = "Нужно войти как администратор."
