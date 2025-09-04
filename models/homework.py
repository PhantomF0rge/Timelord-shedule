from extensions import db

class Homework(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.Date, nullable=True)
