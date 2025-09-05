from __future__ import annotations
import logging
from datetime import datetime, UTC
from datetime import time
from typing import Any, Dict, List, Tuple, Type
from pydantic import ValidationError

from flask import (
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query

from . import bp
from .schemas import (
    AssignmentOut,
    BuildingIn, BuildingOut,
    GroupIn, GroupOut,
    LessonTypeIn, LessonTypeOut,
    RoomIn, RoomOut,
    RoomTypeIn, RoomTypeOut,
    SubjectIn, SubjectOut,
    TeacherIn, TeacherOut,
    TimeSlotIn, TimeSlotOut,
)
from .validators import ensure_timeslot_range
from extensions import db
from models import (
    Assignment,
    Building,
    Group,
    LessonType,
    Room,
    RoomType,
    Subject,
    Teacher,
    TimeSlot,
)

log = logging.getLogger(__name__)

# ----------------------- Helpers -----------------------
def _parse_time(s: str | None) -> time | None:
    if not s:
        return None
    h, m = s.split(":")
    return time(int(h), int(m))

def ok(data: Any, status: int = 200):
    return jsonify(data), status

def created(location: str, data: Any):
    resp = jsonify(data)
    resp.status_code = 201
    resp.headers["Location"] = location
    return resp

def error(msg: str, status: int = 400, code: str | None = None, field: str | None = None):
    payload = {"error": msg}
    if code: payload["code"] = code
    if field: payload["field"] = field
    return jsonify(payload), status

def _paginate(query: Query, serializer, *, page: int, per_page: int, endpoint_fields: List):
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    items = [
        serializer.model_validate(_row_to_dict(r, endpoint_fields)).model_dump(mode="json")
        for r in rows
    ]
    return {"items": items, "meta": {"page": page, "per_page": per_page, "total": total}}

def _row_to_dict(row, fields: List[str]) -> Dict[str, Any]:
    out = {}
    for f in fields:
        val = getattr(row, f)
        out[f] = val
    return out

def _search_filter(model, q: str):
    # РџРѕР»СЏ РґР»СЏ РїРѕРёСЃРєР°
    fields_map = {
        Group: [Group.code, Group.name],
        Teacher: [Teacher.full_name, Teacher.short_name],
        Subject: [Subject.name, Subject.short_name],
        Building: [Building.name, Building.address],
        RoomType: [RoomType.name],
        Room: [Room.number],
        LessonType: [LessonType.name],
        TimeSlot: [TimeSlot.order_no],
    }
    cols = fields_map.get(model, [])
    terms = [str(q).strip()]
    conds = []
    for t in terms:
        for col in cols:
            # int-РїРѕР»СЏ (order_no) вЂ“ СЃСЂР°РІРЅРёРј РєР°Рє СЃС‚СЂРѕРєСѓ С‡РµСЂРµР· cast РІ SQLite РЅРµ РЅСѓР¶РЅРѕ: РїСЂРѕСЃС‚Рѕ РїСЂРёРІРѕРґРёРј РІ Р·Р°РїСЂРѕСЃРµ
            conds.append(col.like(f"%{t}%"))
    return or_(*conds) if conds else None

def _handle_integrity_error(ex: IntegrityError):
    msg = str(ex.orig) if getattr(ex, "orig", None) else str(ex)
    # РќРѕСЂРјР°Р»РёР·СѓРµРј РІ 409 CONFLICT
    return error("Unique constraint violation", status=409, code="UNIQUE_CONSTRAINT", field=None)

def _pydantic_errors_safe(ve: ValidationError):
    errs = ve.errors()  # СЃРїРёСЃРѕРє dict
    for e in errs:
        if "ctx" in e and isinstance(e["ctx"], dict):
            e["ctx"] = {k: str(v) for k, v in e["ctx"].items()}
    return errs

# ----------------------- Admin UI (HTML) -----------------------
@bp.get("/")
def index():
    # РџСЂРѕСЃС‚Р°СЏ СЃС‚СЂР°РЅРёС†Р°-СЂРµРµСЃС‚СЂ СЃРѕ РІРєР»Р°РґРєР°РјРё Рё С„РѕСЂРјР°РјРё СЃРѕР·РґР°РЅРёСЏ
    return render_template("directory/admin.html")

# ----------------------- CRUD JSON API -----------------------
# РЈРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Рµ РјРµС‚РѕРґС‹: РєР°Р¶РґС‹Р№ СЂРµСЃСѓСЂСЃ РїРѕР»СѓС‡РёС‚ 4 endpointвЂ™Р°: list(GET), create(POST), update(PUT), delete(DELETE).
# URL: /directory/api/<resource>[/<id>]

# ---- Groups ----
@bp.get("/api/groups")
def api_groups_list():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.args.get("per_page", 20)))
    s = db.session.query(Group)
    if q:
        cond = _search_filter(Group, q)
        if cond is not None: s = s.filter(cond)
    s = s.order_by(Group.code.asc())
    fields = ["id", "code", "name", "students_count", "education_level"]
    data = _paginate(s, GroupOut, page=page, per_page=per_page, endpoint_fields=fields)
    return ok(data)

@bp.post("/api/groups")
def api_groups_create():
    payload = request.get_json(silent=True) or {}
    parsed = GroupIn.model_validate(payload)
    g = Group(
        code=parsed.code.strip(),
        name=parsed.name,
        students_count=parsed.students_count,
        education_level=parsed.education_level,
    )
    db.session.add(g)
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    out = GroupOut.model_validate({"id": g.id, "code": g.code, "name": g.name,
                                   "students_count": g.students_count, "education_level": g.education_level})
    return created(url_for("directory.api_groups_get", id=g.id), out.model_dump(mode="json"))

@bp.get("/api/groups/<int:id>")
def api_groups_get(id: int):
    g = db.session.get(Group, id) or abort(404)
    out = GroupOut.model_validate({"id": g.id, "code": g.code, "name": g.name,
                                   "students_count": g.students_count, "education_level": g.education_level})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/groups/<int:id>")
def api_groups_update(id: int):
    payload = request.get_json(silent=True) or {}
    parsed = GroupIn.model_validate(payload)
    g = db.session.get(Group, id) or abort(404)
    g.code = parsed.code.strip()
    g.name = parsed.name
    g.students_count = parsed.students_count
    g.education_level = parsed.education_level
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    return ok({"ok": True})

@bp.delete("/api/groups/<int:id>")
def api_groups_delete(id: int):
    g = db.session.get(Group, id) or abort(404)
    db.session.delete(g)
    db.session.commit()
    return "", 204

# ---- Teachers ----
@bp.get("/api/teachers")
def api_teachers_list():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.args.get("per_page", 20)))
    s = db.session.query(Teacher)
    if q:
        cond = _search_filter(Teacher, q)
        if cond is not None: s = s.filter(cond)
    s = s.order_by(Teacher.full_name.asc())
    fields = ["id", "full_name", "short_name", "external_id"]
    data = _paginate(s, TeacherOut, page=page, per_page=per_page, endpoint_fields=fields)
    return ok(data)

@bp.post("/api/teachers")
def api_teachers_create():
    payload = request.get_json(silent=True) or {}
    parsed = TeacherIn.model_validate(payload)
    t = Teacher(full_name=parsed.full_name, short_name=parsed.short_name, external_id=parsed.external_id)
    db.session.add(t)
    db.session.commit()
    out = TeacherOut.model_validate({"id": t.id, "full_name": t.full_name, "short_name": t.short_name, "external_id": t.external_id})
    return created(url_for("directory.api_teachers_get", id=t.id), out.model_dump(mode="json"))

@bp.get("/api/teachers/<int:id>")
def api_teachers_get(id: int):
    t = db.session.get(Teacher, id) or abort(404)
    out = TeacherOut.model_validate({"id": t.id, "full_name": t.full_name, "short_name": t.short_name, "external_id": t.external_id})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/teachers/<int:id>")
def api_teachers_update(id: int):
    payload = request.get_json(silent=True) or {}
    parsed = TeacherIn.model_validate(payload)
    t = db.session.get(Teacher, id) or abort(404)
    t.full_name = parsed.full_name
    t.short_name = parsed.short_name
    t.external_id = parsed.external_id
    db.session.commit()
    return ok({"ok": True})

@bp.delete("/api/teachers/<int:id>")
def api_teachers_delete(id: int):
    t = db.session.get(Teacher, id) or abort(404)
    db.session.delete(t)
    db.session.commit()
    return "", 204

# ---- Subjects ----
@bp.get("/api/subjects")
def api_subjects_list():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.get_json(silent=True) or request.args.get("per_page", 20)))
    s = db.session.query(Subject)
    if q:
        cond = _search_filter(Subject, q)
        if cond is not None: s = s.filter(cond)
    s = s.order_by(Subject.name.asc())
    fields = ["id", "name", "short_name", "external_id"]
    data = _paginate(s, SubjectOut, page=page, per_page=int(per_page), endpoint_fields=fields)
    return ok(data)

@bp.post("/api/subjects")
def api_subjects_create():
    payload = request.get_json(silent=True) or {}
    parsed = SubjectIn.model_validate(payload)
    s = Subject(name=parsed.name, short_name=parsed.short_name, external_id=parsed.external_id)
    db.session.add(s)
    db.session.commit()
    out = SubjectOut.model_validate({"id": s.id, "name": s.name, "short_name": s.short_name, "external_id": s.external_id})
    return created(url_for("directory.api_subjects_get", id=s.id), out.model_dump(mode="json"))

@bp.get("/api/subjects/<int:id>")
def api_subjects_get(id: int):
    s = db.session.get(Subject, id) or abort(404)
    out = SubjectOut.model_validate({"id": s.id, "name": s.name, "short_name": s.short_name, "external_id": s.external_id})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/subjects/<int:id>")
def api_subjects_update(id: int):
    payload = request.get_json(silent=True) or {}
    parsed = SubjectIn.model_validate(payload)
    s = db.session.get(Subject, id) or abort(404)
    s.name = parsed.name
    s.short_name = parsed.short_name
    s.external_id = parsed.external_id
    db.session.commit()
    return ok({"ok": True})

@bp.delete("/api/subjects/<int:id>")
def api_subjects_delete(id: int):
    s = db.session.get(Subject, id) or abort(404)
    db.session.delete(s)
    db.session.commit()
    return "", 204

# ---- Buildings ----
@bp.get("/api/buildings")
def api_buildings_list():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.args.get("per_page", 20)))
    s = db.session.query(Building)
    if q:
        cond = _search_filter(Building, q)
        if cond is not None: s = s.filter(cond)
    s = s.order_by(Building.name.asc())
    fields = ["id", "name", "address", "type"]
    data = _paginate(s, BuildingOut, page=page, per_page=per_page, endpoint_fields=fields)
    return ok(data)

@bp.post("/api/buildings")
def api_buildings_create():
    payload = request.get_json(silent=True) or {}
    parsed = BuildingIn.model_validate(payload)
    b = Building(name=parsed.name, address=parsed.address, type=parsed.type)
    db.session.add(b)
    db.session.commit()
    out = BuildingOut.model_validate({"id": b.id, "name": b.name, "address": b.address, "type": b.type})
    return created(url_for("directory.api_buildings_get", id=b.id), out.model_dump(mode="json"))

@bp.get("/api/buildings/<int:id>")
def api_buildings_get(id: int):
    b = db.session.get(Building, id) or abort(404)
    out = BuildingOut.model_validate({"id": b.id, "name": b.name, "address": b.address, "type": b.type})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/buildings/<int:id>")
def api_buildings_update(id: int):
    payload = request.get_json(silent=True) or {}
    parsed = BuildingIn.model_validate(payload)
    b = db.session.get(Building, id) or abort(404)
    b.name = parsed.name
    b.address = parsed.address
    b.type = parsed.type
    db.session.commit()
    return ok({"ok": True})

@bp.delete("/api/buildings/<int:id>")
def api_buildings_delete(id: int):
    b = db.session.get(Building, id) or abort(404)
    db.session.delete(b)
    db.session.commit()
    return "", 204

# ---- Room Types ----
@bp.get("/api/room-types")
def api_roomtypes_list():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.args.get("per_page", 20)))
    s = db.session.query(RoomType)
    if q:
        cond = _search_filter(RoomType, q)
        if cond is not None: s = s.filter(cond)
    s = s.order_by(RoomType.name.asc())
    fields = ["id", "name", "requires_computers", "sports"]
    data = _paginate(s, RoomTypeOut, page=page, per_page=per_page, endpoint_fields=fields)
    return ok(data)

@bp.post("/api/room-types")
def api_roomtypes_create():
    payload = request.get_json(silent=True) or {}
    parsed = RoomTypeIn.model_validate(payload)
    r = RoomType(name=parsed.name, requires_computers=parsed.requires_computers, sports=parsed.sports)
    db.session.add(r)
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    out = RoomTypeOut.model_validate({"id": r.id, "name": r.name, "requires_computers": r.requires_computers, "sports": r.sports})
    return created(url_for("directory.api_roomtypes_get", id=r.id), out.model_dump(mode="json"))

@bp.get("/api/room-types/<int:id>")
def api_roomtypes_get(id: int):
    r = db.session.get(RoomType, id) or abort(404)
    out = RoomTypeOut.model_validate({"id": r.id, "name": r.name, "requires_computers": r.requires_computers, "sports": r.sports})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/room-types/<int:id>")
def api_roomtypes_update(id: int):
    payload = request.get_json(silent=True) or {}
    parsed = RoomTypeIn.model_validate(payload)
    r = db.session.get(RoomType, id) or abort(404)
    r.name = parsed.name
    r.requires_computers = parsed.requires_computers
    r.sports = parsed.sports
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    return ok({"ok": True})

@bp.delete("/api/room-types/<int:id>")
def api_roomtypes_delete(id: int):
    r = db.session.get(RoomType, id) or abort(404)
    db.session.delete(r)
    db.session.commit()
    return "", 204

# ---- Rooms ----
@bp.get("/api/rooms")
def api_rooms_list():
    q = request.args.get("q", "")
    building_id = request.args.get("building_id")
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.args.get("per_page", 20)))
    s = db.session.query(Room)
    if building_id:
        s = s.filter(Room.building_id == int(building_id))
    if q:
        cond = _search_filter(Room, q)
        if cond is not None: s = s.filter(cond)
    s = s.order_by(Room.number.asc())
    fields = ["id", "building_id", "number", "capacity", "room_type_id", "computers_count"]
    data = _paginate(s, RoomOut, page=page, per_page=per_page, endpoint_fields=fields)
    return ok(data)

@bp.post("/api/rooms")
def api_rooms_create():
    payload = request.get_json(silent=True) or {}
    parsed = RoomIn.model_validate(payload)
    if parsed.capacity < 0 or parsed.computers_count < 0:
        return error("capacity/computers_count must be >= 0", field="capacity", status=400)
    r = Room(
        building_id=parsed.building_id,
        number=parsed.number.strip(),
        capacity=parsed.capacity,
        room_type_id=parsed.room_type_id,
        computers_count=parsed.computers_count,
    )
    db.session.add(r)
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)  # Р»РѕРІРёС‚ СѓРЅРёРєР°Р»СЊРЅРѕСЃС‚СЊ (building_id, number)
    out = RoomOut.model_validate({"id": r.id, "building_id": r.building_id, "number": r.number,
                                  "capacity": r.capacity, "room_type_id": r.room_type_id,
                                  "computers_count": r.computers_count})
    return created(url_for("directory.api_rooms_get", id=r.id), out.model_dump(mode="json"))

@bp.get("/api/rooms/<int:id>")
def api_rooms_get(id: int):
    r = db.session.get(Room, id) or abort(404)
    out = RoomOut.model_validate({"id": r.id, "building_id": r.building_id, "number": r.number,
                                  "capacity": r.capacity, "room_type_id": r.room_type_id,
                                  "computers_count": r.computers_count})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/rooms/<int:id>")
def api_rooms_update(id: int):
    payload = request.get_json(silent=True) or {}
    parsed = RoomIn.model_validate(payload)
    if parsed.capacity < 0 or parsed.computers_count < 0:
        return error("capacity/computers_count must be >= 0", field="capacity", status=400)
    r = db.session.get(Room, id) or abort(404)
    r.building_id = parsed.building_id
    r.number = parsed.number.strip()
    r.capacity = parsed.capacity
    r.room_type_id = parsed.room_type_id
    r.computers_count = parsed.computers_count
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    return ok({"ok": True})

@bp.delete("/api/rooms/<int:id>")
def api_rooms_delete(id: int):
    r = db.session.get(Room, id) or abort(404)
    db.session.delete(r)
    db.session.commit()
    return "", 204

# ---- Lesson Types ----
@bp.get("/api/lesson-types")
def api_lesson_types_list():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.args.get("per_page", 20)))
    s = db.session.query(LessonType)
    if q:
        cond = _search_filter(LessonType, q)
        if cond is not None: s = s.filter(cond)
    s = s.order_by(LessonType.name.asc())
    fields = ["id", "name"]
    data = _paginate(s, LessonTypeOut, page=page, per_page=per_page, endpoint_fields=fields)
    return ok(data)

@bp.post("/api/lesson-types")
def api_lesson_types_create():
    payload = request.get_json(silent=True) or {}
    parsed = LessonTypeIn.model_validate(payload)
    lt = LessonType(name=parsed.name)
    db.session.add(lt)
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    out = LessonTypeOut.model_validate({"id": lt.id, "name": lt.name})
    return created(url_for("directory.api_lesson_types_get", id=lt.id), out.model_dump(mode="json"))

@bp.get("/api/lesson-types/<int:id>")
def api_lesson_types_get(id: int):
    lt = db.session.get(LessonType, id) or abort(404)
    out = LessonTypeOut.model_validate({"id": lt.id, "name": lt.name})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/lesson-types/<int:id>")
def api_lesson_types_update(id: int):
    payload = request.get_json(silent=True) or {}
    parsed = LessonTypeIn.model_validate(payload)
    lt = db.session.get(LessonType, id) or abort(404)
    lt.name = parsed.name
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    return ok({"ok": True})

@bp.delete("/api/lesson-types/<int:id>")
def api_lesson_types_delete(id: int):
    lt = db.session.get(LessonType, id) or abort(404)
    db.session.delete(lt)
    db.session.commit()
    return "", 204

# ---- Time Slots ----
@bp.get("/api/time-slots")
def api_time_slots_list():
    page = int(request.args.get("page", 1))
    per_page = min(100, int(request.args.get("per_page", 50)))
    s = db.session.query(TimeSlot).order_by(TimeSlot.order_no.asc())
    fields = ["id", "order_no", "start_time", "end_time"]
    data = _paginate(s, TimeSlotOut, page=page, per_page=per_page, endpoint_fields=fields)
    return ok(data)

@bp.post("/api/time-slots")
def api_time_slots_create():
    payload = request.get_json(silent=True) or {}
    try:
        parsed = TimeSlotIn.model_validate(payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": _pydantic_errors_safe(ve)}), 422

    ts = TimeSlot(order_no=parsed.order_no, start_time=parsed.start_time, end_time=parsed.end_time)
    db.session.add(ts)
    try:
        db.session.commit()
    except IntegrityError as ex:
        db.session.rollback()
        return _handle_integrity_error(ex)
    out = TimeSlotOut.model_validate({"id": ts.id, "order_no": ts.order_no, "start_time": ts.start_time, "end_time": ts.end_time})
    return created(url_for("directory.api_time_slots_get", id=ts.id), out.model_dump(mode="json"))

@bp.get("/api/time-slots/<int:id>")
def api_time_slots_get(id: int):
    ts = db.session.get(TimeSlot, id) or abort(404)
    out = TimeSlotOut.model_validate({"id": ts.id, "order_no": ts.order_no, "start_time": ts.start_time, "end_time": ts.end_time})
    return ok(out.model_dump(mode="json"))

@bp.put("/api/time-slots/<int:id>")
def api_time_slots_update(id: int):
    payload = request.get_json(silent=True) or {}
    try:
        parsed = TimeSlotIn.model_validate(payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": _pydantic_errors_safe(ve)}), 422

    ts = db.session.get(TimeSlot, id) or abort(404)
    ts.order_no = parsed.order_no
    ts.start_time = parsed.start_time
    ts.end_time = parsed.end_time
    db.session.commit()
    return ok({"ok": True})

@bp.delete("/api/time-slots/<int:id>")
def api_time_slots_delete(id: int):
    ts = db.session.get(TimeSlot, id) or abort(404)
    db.session.delete(ts)
    db.session.commit()
    return "", 204
