from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    # пока нет реальной авторизации — никого не загружаем
    return None

@login_manager.request_loader
def load_user_from_request(request):
    # и из запроса никого не логиним
    return None