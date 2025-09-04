from extensions import db

class Curriculum(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    total_hours = db.Column(db.Integer, nullable=False, default=0)
    hours_per_week = db.Column(db.Integer, nullable=True)
    __table_args__ = (db.UniqueConstraint("group_id", "subject_id", name="uq_curriculum_group_subject"),)
