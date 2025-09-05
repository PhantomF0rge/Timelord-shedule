# scripts/dev_db_init.py
from werkzeug.security import generate_password_hash
from app import create_app
from extensions import db
from models import User  # и другие модели не нужны для create_all()

app = create_app("dev")
with app.app_context():
    db.create_all()

    def ensure_user(email, role, password="pass"):
        if not User.query.filter_by(email=email).first():
            db.session.add(User(
                email=email,
                role=role,
                password_hash=generate_password_hash(password)
            ))

    ensure_user("admin@example.com", "ADMIN")
    ensure_user("t1@example.com", "TEACHER")

    db.session.commit()
    print("DB initialized, users created: admin@example.com / pass, t1@example.com / pass")