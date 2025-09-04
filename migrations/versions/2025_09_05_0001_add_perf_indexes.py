"""add performance indexes (conditional, safe for sqlite)"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "2025_09_05_0001"
down_revision = None
branch_labels = None
depends_on = None

def _table_exists(conn, name):
    # sqlite
    res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name}).fetchone()
    return res is not None

def _columns_exist(conn, table, cols):
    rows = conn.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
    names = {r[1] for r in rows}
    return all(c in names for c in cols)

def _create_index_if_absent(conn, idx_name, table, cols, unique=False, quote_table=False):
    if not _table_exists(conn, table):
        return False
    if not _columns_exist(conn, table, cols):
        return False
    uq = "UNIQUE " if unique else ""
    tname = f'"{table}"' if quote_table else table
    cols_sql = ", ".join(cols)
    conn.execute(text(f"CREATE {uq}INDEX IF NOT EXISTS {idx_name} ON {tname} ({cols_sql})"))
    return True

def upgrade():
    bind = op.get_bind()

    # groups.code UNIQUE (и альтернатива "group".code)
    if not _create_index_if_absent(bind, "uq_groups_code", "groups", ["code"], unique=True):
        _create_index_if_absent(bind, "uq_group_code", "group", ["code"], unique=True, quote_table=True)

    # teachers.full_name + возможные поля ФИО
    _create_index_if_absent(bind, "ix_teachers_full_name", "teachers", ["full_name"])
    for col in ("last_name", "first_name", "middle_name"):
        _create_index_if_absent(bind, f"ix_teachers_{col}", "teachers", [col])

    # subjects.name
    _create_index_if_absent(bind, "ix_subjects_name", "subjects", ["name"])

    # timeslot.order_no (разные варианты имён таблицы)
    created = False
    for t in ("timeslot", "time_slot", "timeslots", "time_slots"):
        if _create_index_if_absent(bind, f"ix_{t}_order_no", t, ["order_no"]):
            created = True
            break
    if not created:
        # на крайний — попробуем field "order"
        for t in ("timeslot", "time_slot", "timeslots", "time_slots"):
            if _create_index_if_absent(bind, f"ix_{t}_order", t, ["order"]):
                break

    # lesson.date
    if not _create_index_if_absent(bind, "ix_lessons_date", "lessons", ["date"]):
        _create_index_if_absent(bind, "ix_lesson_date", "lesson", ["date"])

    # (lesson.group_id, lesson.date)
    if not _create_index_if_absent(bind, "ix_lessons_group_date", "lessons", ["group_id", "date"]):
        _create_index_if_absent(bind, "ix_lesson_group_date", "lesson", ["group_id", "date"])

    # (lesson.teacher_id, lesson.date)
    if not _create_index_if_absent(bind, "ix_lessons_teacher_date", "lessons", ["teacher_id", "date"]):
        _create_index_if_absent(bind, "ix_lesson_teacher_date", "lesson", ["teacher_id", "date"])

def downgrade():
    bind = op.get_bind()
    # Безопасно: просто дропаем все потенциальные имена индексов
    possible = [
        "uq_groups_code", "uq_group_code",
        "ix_teachers_full_name", "ix_teachers_last_name", "ix_teachers_first_name", "ix_teachers_middle_name",
        "ix_subjects_name",
        "ix_timeslot_order_no", "ix_time_slot_order_no", "ix_timeslots_order_no", "ix_time_slots_order_no",
        "ix_timeslot_order", "ix_time_slot_order", "ix_timeslots_order", "ix_time_slots_order",
        "ix_lessons_date", "ix_lesson_date",
        "ix_lessons_group_date", "ix_lesson_group_date",
        "ix_lessons_teacher_date", "ix_lesson_teacher_date",
    ]
    for idx in possible:
        try:
            bind.execute(text(f'DROP INDEX IF EXISTS {idx}'))
        except Exception:
            pass
