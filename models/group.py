from extensions import db
import enum

class EducationLevel(str, enum.Enum):
    VO = "VO"   # высшее
    SPO = "SPO" # среднее проф.

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    students_count = db.Column(db.Integer, nullable=False, default=25)
    education_level = db.Column(db.Enum(EducationLevel), nullable=False, default=EducationLevel.SPO)
