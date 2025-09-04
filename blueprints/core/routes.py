from flask import render_template
from . import bp

@bp.get("/")
def index():
    # Главная с новым UI
    return render_template("index.html")

@bp.get("/health")
def health():
    return {"status": "ok"}
