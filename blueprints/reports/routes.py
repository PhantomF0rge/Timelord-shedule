# blueprints/reports/routes.py
from __future__ import annotations
from datetime import date
from flask import Blueprint, request, Response, abort
from flask_login import login_required
from blueprints.auth.routes import admin_required

from .services import weekly_schedule_csv, teacher_hours_csv, room_utilization_csv

bp = Blueprint("reports", __name__, template_folder="../../templates", static_folder="../../static")
api_bp = Blueprint("reports_api", __name__)

def _parse_dates() -> tuple[date, date]:
    try:
        d_from = date.fromisoformat(str(request.args.get("date_from")))
        d_to   = date.fromisoformat(str(request.args.get("date_to")))
    except Exception:
        abort(400)
    if d_to < d_from:
        d_from, d_to = d_to, d_from
    return d_from, d_to

def _csv_resp(content: str, filename: str) -> Response:
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@api_bp.get("/admin/reports/weekly-schedule.csv")
@login_required
@admin_required
def weekly_schedule():
    scope = (request.args.get("scope") or "").lower()  # group|teacher|building
    try:
        scope_id = int(request.args.get("id", "0"))
    except Exception:
        abort(400)
    d_from, d_to = _parse_dates()
    csv_data = weekly_schedule_csv(scope, scope_id, d_from, d_to)
    return _csv_resp(csv_data, f"weekly_schedule_{scope}_{scope_id}.csv")

@api_bp.get("/admin/reports/teacher-hours.csv")
@login_required
@admin_required
def teacher_hours():
    d_from, d_to = _parse_dates()
    raw = (request.args.get("teacher_ids") or "").strip()
    ids = [int(x) for x in raw.split(",") if x.strip().isdigit()] if raw else None
    csv_data = teacher_hours_csv(d_from, d_to, ids)
    return _csv_resp(csv_data, "teacher_hours.csv")

@api_bp.get("/admin/reports/room-utilization.csv")
@login_required
@admin_required
def room_utilization():
    d_from, d_to = _parse_dates()
    b_id = request.args.get("building_id")
    bid = int(b_id) if (b_id and b_id.isdigit()) else None
    csv_data = room_utilization_csv(d_from, d_to, bid)
    return _csv_resp(csv_data, f"room_utilization{'_'+str(bid) if bid else ''}.csv")
