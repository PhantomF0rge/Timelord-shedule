"""search indexes

Revision ID: 0003
Revises: 0002
Create Date: 2025-09-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # groups: index on code (если нет)
    existing = {ix["name"] for ix in insp.get_indexes("groups")}
    if "ix_groups_code" not in existing:
        op.create_index("ix_groups_code", "groups", ["code"], unique=False)

    # (на учителях/предметах индексы уже добавлены в 0002:
    # ix_teachers_full_name, ix_subjects_name)

def downgrade():
    op.drop_index("ix_groups_code", table_name="groups")
