from extensions import db
from flask_login import UserMixin
import enum

class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    TEACHER = "TEACHER"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.TEACHER)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
