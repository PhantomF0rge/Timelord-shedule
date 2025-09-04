from extensions import db
import enum

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    short_name = db.Column(db.String(128), nullable=True)

class TeacherAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0=Mon..6=Sun
    available_from = db.Column(db.Time, nullable=True)
    available_to = db.Column(db.Time, nullable=True)
    is_day_off = db.Column(db.Boolean, default=False)

class WorkloadLimit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    hours_per_week = db.Column(db.Float, nullable=False, default=18.0)
