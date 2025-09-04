from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import func
from extensions import db
from . import bp

def _try_import(module_path, class_name):
    try:
        mod = __import__(module_path, fromlist=[class_name])
        return getattr(mod, class_name, None)
    except Exception:
        return None

def M():
    return {
        "User": _try_import("models.user", "User"),
        "Group": _try_import("models.group", "Group") or _try_import("models.groups", "Group"),
        "Teacher": _try_import("models.teacher", "Teacher") or _try_import("models.teachers", "Teacher"),
        "Subject": _try_import("models.subject", "Subject") or _try_import("models.subjects", "Subject"),
        "Room": _try_import("models.room", "Room") or _try_import("models.rooms", "Room"),
        "Lesson": _try_import("models.lesson", "Lesson") or _try_import("models.lessons", "Lesson"),
    }

def admin_required(view):
    @login_required
    def wrapper(*args, **kwargs):
        if not (hasattr(current_user, "role") and current_user.role == "admin"):
            flash("Требуются права администратора", "error")
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper

# --- helpers ---
def _normalize_edu(v: str | None) -> str | None:
    if not v:
        return None
    s = v.strip().upper()
    if s in ("СПО", "SPO"):
        return "SPO"
    if s in ("ВО", "VO"):
        return "VO"
    return None

# -------- аутентификация --------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and getattr(current_user, "role", None) == "admin":
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        User = M()["User"]
        user = db.session.query(User).filter(func.lower(User.username) == username.lower()).first() if User else None
        if user and user.check_password(password) and user.role == "admin":
            login_user(user, remember=True)
            return redirect(url_for("admin.dashboard"))
        flash("Неверный логин или пароль", "error")
    return render_template("admin/login.html")

@bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))

# -------- главная админки --------
@bp.get("/")
@admin_required
def dashboard():
    MM = M()
    counts = {}
    for key in ("Group", "Teacher", "Subject", "Room", "Lesson"):
        model = MM[key]
        if model is None:
            counts[key] = 0
        else:
            counts[key] = db.session.query(model).count()
    return render_template("admin/dashboard.html", counts=counts)

# -------- группы --------
@bp.get("/groups")
@admin_required
def groups_list():
    Group = M()["Group"]
    items = db.session.query(Group).order_by(Group.code.asc()).all() if Group else []
    return render_template("admin/groups_list.html", items=items)

@bp.route("/groups/new", methods=["GET", "POST"])
@admin_required
def group_create():
    Group = M()["Group"]
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        name = (request.form.get("name") or "").strip()
        students = int(request.form.get("students_count") or 0)
        edu_level = _normalize_edu(request.form.get("education_level"))
        g = Group(code=code, name=name, students_count=students)
        if edu_level is not None and hasattr(Group, "education_level"):
            g.education_level = edu_level
        db.session.add(g)
        db.session.commit()
        return redirect(url_for("admin.groups_list"))
    return render_template("admin/group_form.html", item=None)

@bp.route("/groups/<int:gid>/edit", methods=["GET", "POST"])
@admin_required
def group_edit(gid: int):
    Group = M()["Group"]
    g = db.session.get(Group, gid)
    if not g:
        return redirect(url_for("admin.groups_list"))
    if request.method == "POST":
        g.code = (request.form.get("code") or "").strip()
        g.name = (request.form.get("name") or "").strip()
        g.students_count = int(request.form.get("students_count") or 0)
        edu_level = _normalize_edu(request.form.get("education_level"))
        if edu_level is not None and hasattr(Group, "education_level"):
            g.education_level = edu_level
        db.session.commit()
        return redirect(url_for("admin.groups_list"))
    return render_template("admin/group_form.html", item=g)
