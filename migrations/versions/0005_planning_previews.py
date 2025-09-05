"""add planning_previews"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0001"

def upgrade():
    op.create_table(
        "planning_previews",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )

def downgrade():
    op.drop_table("planning_previews")
