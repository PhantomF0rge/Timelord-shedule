from extensions import db

class RoomType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    requires_computers = db.Column(db.Boolean, default=False)
    is_sports = db.Column(db.Boolean, default=False)
