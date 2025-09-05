# models/planning.py
from __future__ import annotations
from datetime import datetime
import uuid
from extensions import db

class PlanningPreview(db.Model):
    __tablename__ = "planning_previews"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Полный снимок предпросмотра, чтобы не тащить кучу таблиц
    payload = db.Column(db.JSON, nullable=False, default=dict)
