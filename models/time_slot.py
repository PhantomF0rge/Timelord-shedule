from extensions import db

class TimeSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.Integer, nullable=False)  # 1..N
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    __table_args__ = (db.UniqueConstraint("order_no", "start_time", "end_time", name="uq_timeslot"),)
