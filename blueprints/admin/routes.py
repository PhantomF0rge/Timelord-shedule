from flask import jsonify
from . import bp

@bp.route("/_alive")
def _alive():
    return jsonify(module=bp.name, ok=True)