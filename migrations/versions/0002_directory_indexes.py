"""directory search indexes and uniques

Revision ID: 0002
Revises: 0001
Create Date: 2025-09-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    # Индексы под поиск
    op.create_index("ix_teachers_full_name", "teachers", ["full_name"])
    op.create_index("ix_subjects_name", "subjects", ["name"])
    op.create_index("ix_buildings_name", "buildings", ["name"])
    op.create_index("ix_rooms_number", "rooms", ["number"])
    op.create_index("ix_lesson_types_name", "lesson_types", ["name"], unique=True)
    op.create_index("ix_room_types_name", "room_types", ["name"], unique=True)

def downgrade():
    op.drop_index("ix_room_types_name", table_name="room_types")
    op.drop_index("ix_lesson_types_name", table_name="lesson_types")
    op.drop_index("ix_rooms_number", table_name="rooms")
    op.drop_index("ix_buildings_name", table_name="buildings")
    op.drop_index("ix_subjects_name", table_name="subjects")
    op.drop_index("ix_teachers_full_name", table_name="teachers")