from flask import render_template, request
from . import bp

@bp.get("/")
def index():
    # In future: auto-load schedule for last_group from localStorage via JS
    return render_template("base.html")

@bp.get("/health")
def health():
    return {"status":"ok"}
