from extensions import db

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    time_slot_id = db.Column(db.Integer, db.ForeignKey("time_slot.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    lesson_type_id = db.Column(db.Integer, db.ForeignKey("lesson_type.id"), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=True)
    is_remote = db.Column(db.Boolean, default=False)
    note = db.Column(db.String(255), nullable=True)
    __table_args__ = (db.UniqueConstraint("date", "time_slot_id", "group_id", name="uq_sched_group_slot_date"),)
