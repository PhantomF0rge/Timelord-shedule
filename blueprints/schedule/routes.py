from flask import request, jsonify, render_template
from . import bp

@bp.get("/")
def placeholder_index():
    return jsonify({"module": "schedule", "status": "stub"})
