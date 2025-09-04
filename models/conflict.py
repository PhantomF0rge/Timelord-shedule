from extensions import db
import enum

class ConflictStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"

class Conflict(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(64), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"), nullable=True)
    payload_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(ConflictStatus), nullable=False, default=ConflictStatus.OPEN)
