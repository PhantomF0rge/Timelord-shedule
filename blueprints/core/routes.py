from flask import render_template, jsonify, current_app
from . import bp

@bp.route("/health")
def health():
    return jsonify(status="ok", version=current_app.config.get("APP_VERSION", "dev"))

@bp.route("/")
def index():
    return render_template("index.html")
