from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import and_
from extensions import db
from . import bp

# --- безопасный импорт моделей (поддерживает разные имена файлов/классов) ---
def _safe_import(path, name):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name, None)
    except Exception:
        return None

Group      = _safe_import("models.group", "Group") or _safe_import("models.groups", "Group")
Teacher    = _safe_import("models.teacher", "Teacher") or _safe_import("models.teachers", "Teacher")
Subject    = _safe_import("models.subject", "Subject") or _safe_import("models.subjects", "Subject")
Building   = _safe_import("models.building", "Building")
RoomType   = _safe_import("models.room_type", "RoomType") or _safe_import("models.roomtype", "RoomType")
Room       = _safe_import("models.room", "Room") or _safe_import("models.rooms", "Room")

def admin_required(view):
    @login_required
    def wrapper(*args, **kwargs):
        role = getattr(current_user, "role", None)
        if role not in ("admin", "superadmin"):
            abort(403)
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper

# ----------------- DASH -----------------
@bp.get("/")
@admin_required
def index():
    return render_template("admin/index.html")

# ----------------- GROUPS (у тебя уже есть список — оставляем) -----------------
@bp.get("/groups")
@admin_required
def groups_list():
    items = db.session.query(Group).order_by(getattr(Group, "code").asc()).all() if Group else []
    return render_template("admin/groups_list.html", items=items, model=Group)

@bp.route("/groups/new", methods=["GET", "POST"])
@bp.route("/groups/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def groups_form(item_id=None):
    if not Group:
        abort(501, description="Model Group is missing")
    item = db.session.get(Group, item_id) if item_id else Group()
    if request.method == "POST":
        form = request.form
        # безопасно выставляем только существующие поля
        if hasattr(item, "code"):             item.code = form.get("code", "").strip()
        if hasattr(item, "name"):             item.name = form.get("name", "").strip()
        if hasattr(item, "students_count"):   item.students_count = int(form.get("students_count") or 0)
        if hasattr(item, "education_level"):  item.education_level = form.get("education_level") or None
        if hasattr(item, "label"):            item.label = form.get("label") or item.name or item.code

        db.session.add(item); db.session.commit()
        flash("Группа сохранена", "success")
        return redirect(url_for("admin.groups_list"))
    return render_template("admin/group_form.html", item=item, model=Group)

@bp.post("/groups/<int:item_id>/delete")
@admin_required
def groups_delete(item_id):
    if not Group:
        abort(501)
    item = db.session.get(Group, item_id)
    if not item:
        abort(404)
    db.session.delete(item); db.session.commit()
    flash("Группа удалена", "success")
    return redirect(url_for("admin.groups_list"))

# ----------------- TEACHERS -----------------
@bp.get("/teachers")
@admin_required
def teachers_list():
    if not Teacher:
        abort(501, description="Model Teacher is missing")
    # сортируем по full_name если есть, иначе по last_name/first_name
    if hasattr(Teacher, "full_name"):
        items = db.session.query(Teacher).order_by(getattr(Teacher, "full_name").asc()).all()
    elif hasattr(Teacher, "last_name"):
        items = db.session.query(Teacher).order_by(getattr(Teacher, "last_name").asc()).all()
    else:
        items = db.session.query(Teacher).all()
    return render_template("admin/teachers_list.html", items=items, model=Teacher)

@bp.route("/teachers/new", methods=["GET", "POST"])
@bp.route("/teachers/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def teachers_form(item_id=None):
    if not Teacher:
        abort(501)
    item = db.session.get(Teacher, item_id) if item_id else Teacher()
    if request.method == "POST":
        f = request.form
        # поддерживаем обе схемы: full_name ИЛИ отдельные ФИО
        if hasattr(item, "full_name"):
            item.full_name = f.get("full_name", "").strip() or "Без имени"
        if hasattr(item, "last_name"):
            item.last_name = f.get("last_name", "").strip()
        if hasattr(item, "first_name"):
            item.first_name = f.get("first_name", "").strip()
        if hasattr(item, "middle_name"):
            item.middle_name = f.get("middle_name", "").strip()
        # необязательные поля:
        if hasattr(item, "weekly_hours_limit"):
            try:
                item.weekly_hours_limit = int(f.get("weekly_hours_limit") or 0)
            except ValueError:
                item.weekly_hours_limit = 0

        db.session.add(item); db.session.commit()
        flash("Преподаватель сохранён", "success")
        return redirect(url_for("admin.teachers_list"))

    return render_template("admin/teacher_form.html", item=item, model=Teacher)

@bp.post("/teachers/<int:item_id>/delete")
@admin_required
def teachers_delete(item_id):
    if not Teacher:
        abort(501)
    item = db.session.get(Teacher, item_id)
    if not item:
        abort(404)
    db.session.delete(item); db.session.commit()
    flash("Удалено", "success")
    return redirect(url_for("admin.teachers_list"))

# ----------------- SUBJECTS -----------------
@bp.get("/subjects")
@admin_required
def subjects_list():
    if not Subject:
        abort(501, description="Model Subject is missing")
    # сортируем по name, если есть
    if hasattr(Subject, "name"):
        items = db.session.query(Subject).order_by(getattr(Subject, "name").asc()).all()
    else:
        items = db.session.query(Subject).all()
    return render_template("admin/subjects_list.html", items=items, model=Subject)

@bp.route("/subjects/new", methods=["GET", "POST"])
@bp.route("/subjects/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def subjects_form(item_id=None):
    if not Subject:
        abort(501)
    item = db.session.get(Subject, item_id) if item_id else Subject()
    if request.method == "POST":
        f = request.form
        if hasattr(item, "name"):  item.name  = f.get("name", "").strip() or "Без названия"
        if hasattr(item, "title"): item.title = f.get("title", "").strip() or item.name
        db.session.add(item); db.session.commit()
        flash("Дисциплина сохранена", "success")
        return redirect(url_for("admin.subjects_list"))
    return render_template("admin/subject_form.html", item=item, model=Subject)

@bp.post("/subjects/<int:item_id>/delete")
@admin_required
def subjects_delete(item_id):
    if not Subject:
        abort(501)
    item = db.session.get(Subject, item_id)
    if not item:
        abort(404)
    db.session.delete(item); db.session.commit()
    flash("Удалено", "success")
    return redirect(url_for("admin.subjects_list"))

# ----------------- ROOMS -----------------
@bp.get("/rooms")
@admin_required
def rooms_list():
    if not Room:
        abort(501, description="Model Room is missing")
    # простая сортировка по number
    items = db.session.query(Room).order_by(getattr(Room, "number").asc()).all() if hasattr(Room, "number") else db.session.query(Room).all()
    # подтянем словари для отображения
    buildings = db.session.query(Building).all() if Building else []
    room_types = db.session.query(RoomType).all() if RoomType else []
    bmap = {getattr(b, "id"): getattr(b, "name", getattr(b, "title", "")) for b in buildings}
    tmap = {getattr(t, "id"): getattr(t, "title", getattr(t, "name", "")) for t in room_types}
    return render_template("admin/rooms_list.html", items=items, model=Room, bmap=bmap, tmap=tmap)

@bp.route("/rooms/new", methods=["GET", "POST"])
@bp.route("/rooms/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def rooms_form(item_id=None):
    if not Room:
        abort(501)
    item = db.session.get(Room, item_id) if item_id else Room()

    # справочники для select
    buildings = db.session.query(Building).all() if Building else []
    room_types = db.session.query(RoomType).all() if RoomType else []

    if request.method == "POST":
        f = request.form
        if hasattr(item, "number"):           item.number = f.get("number", "").strip()
        if hasattr(item, "capacity"):         item.capacity = int(f.get("capacity") or 0)
        if hasattr(item, "computers_count"):  item.computers_count = int(f.get("computers_count") or f.get("computers") or 0)
        if hasattr(item, "computers"):        item.computers = int(f.get("computers") or f.get("computers_count") or 0)

        if hasattr(item, "building_id"):
            try:
                item.building_id = int(f.get("building_id") or 0) or None
            except ValueError:
                item.building_id = None

        if hasattr(item, "room_type_id"):
            try:
                item.room_type_id = int(f.get("room_type_id") or 0) or None
            except ValueError:
                item.room_type_id = None

        db.session.add(item); db.session.commit()
        flash("Аудитория сохранена", "success")
        return redirect(url_for("admin.rooms_list"))

    return render_template("admin/room_form.html", item=item, model=Room, buildings=buildings, room_types=room_types)

@bp.post("/rooms/<int:item_id>/delete")
@admin_required
def rooms_delete(item_id):
    if not Room:
        abort(501)
    item = db.session.get(Room, item_id)
    if not item:
        abort(404)
    db.session.delete(item); db.session.commit()
    flash("Удалено", "success")
    return redirect(url_for("admin.rooms_list"))
