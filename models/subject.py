from extensions import db

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    short_name = db.Column(db.String(64), nullable=True)
    requires_computers = db.Column(db.Boolean, default=False)
