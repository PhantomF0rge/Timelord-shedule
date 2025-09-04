from extensions import db

class LessonType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)  # лекция, практика, зачет, экзамен
