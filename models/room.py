from extensions import db

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("building.id"), nullable=False)
    number = db.Column(db.String(64), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=30)
    room_type_id = db.Column(db.Integer, db.ForeignKey("room_type.id"), nullable=True)
    computers_count = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint("building_id", "number", name="uq_room_building_number"),)
