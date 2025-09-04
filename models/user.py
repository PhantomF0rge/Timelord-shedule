from enum import Enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

class Role(str, Enum):
    ADMIN = "admin"
    TEACHER = "teacher"

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # строковое поле, чтобы не зависеть от конкретного типа БД
    role = db.Column(db.String(16), index=True, nullable=False, default=Role.ADMIN.value)
    is_active_flag = db.Column(db.Boolean, default=True, nullable=False)

    # helpers
    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # Flask-Login ожидает .is_active
    @property
    def is_active(self):
        return bool(self.is_active_flag)

@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None
