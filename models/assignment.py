from extensions import db

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("teacher_id", "group_id", "subject_id", name="uq_assignment_triplet"),)
