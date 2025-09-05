from __future__ import annotations
import json, logging
from datetime import datetime
from uuid import uuid4

from flask import g, jsonify, render_template, request
from werkzeug.wrappers.response import Response

from flask_wtf.csrf import generate_csrf
from extensions import csrf

from . import bp                 # используем bp из __init__.py
from .filters import register_filters
from . import api_bp

VISITOR_COOKIE = "visitor_id"
VISITOR_MAX_AGE = 60 * 60 * 24 * 180  # 180 дней

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("event","path","method","status","duration_ms","visitor_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)

def _setup_structured_logging(app):
    logger = app.logger
    has_json = any(
        isinstance(h, logging.StreamHandler)
        and isinstance(getattr(h, "formatter", None), JSONFormatter)
        for h in logger.handlers
    )
    if not has_json:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

@api_bp.get("/csrf")
@csrf.exempt          # токен выдаём без проверки
def get_csrf():
    token = generate_csrf()
    resp = jsonify({"csrf": token})
    resp.set_cookie("csrf_token", token, samesite="Lax")
    return resp

@bp.before_app_request
def _ensure_visitor_and_start_timer():
    g._req_start = datetime.utcnow()
    vid = request.cookies.get(VISITOR_COOKIE)
    if not vid:
        vid = uuid4().hex
        g._set_visitor_cookie = vid
    g.visitor_id = vid

@bp.after_app_request
def _maybe_set_cookie_and_log(response: Response):
    if getattr(g, "_set_visitor_cookie", None):
        response.set_cookie(
            VISITOR_COOKIE,
            g._set_visitor_cookie,
            max_age=VISITOR_MAX_AGE,
            httponly=False,
            secure=request.is_secure,
            samesite="Lax",
            path="/",
        )
    try:
        duration_ms = int((datetime.utcnow() - g._req_start).total_seconds() * 1000)
    except Exception:
        duration_ms = None
    extra = {
        "event":"http_request",
        "path":request.path,
        "method":request.method,
        "status":response.status_code,
        "duration_ms":duration_ms,
        "visitor_id":getattr(g, "visitor_id", None),
    }
    # логгер уже настроен в _on_register
    logging.getLogger().info("request handled", extra=extra)
    return response

@bp.record_once
def _on_register(state):
    app = state.app
    _setup_structured_logging(app)
    register_filters(app)

@bp.get("/")
def home():
    return render_template("core/index.html")

@bp.get("/health")
def health():
    return jsonify({
        "status":"ok",
        "ts": datetime.utcnow().isoformat(timespec="seconds")+"Z",
        "visitor_id": getattr(g, "visitor_id", None),
    })