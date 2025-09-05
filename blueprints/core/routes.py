from flask import render_template, jsonify
from . import bp

@bp.get("/")
def index():
    return render_template("core/index.html")

@bp.get("/health")
def health():
    return jsonify(status="ok")
