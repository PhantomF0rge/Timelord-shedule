from extensions import db

class Building(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    edu_type = db.Column(db.String(32), nullable=True)  # VO/SPO marker (optional string)
