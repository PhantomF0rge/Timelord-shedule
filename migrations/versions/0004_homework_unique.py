"""homework unique on schedule_id"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("homeworks") as batch:
        batch.create_unique_constraint("uq_homeworks_schedule", ["schedule_id"])

def downgrade():
    with op.batch_alter_table("homeworks") as batch:
        batch.drop_constraint("uq_homeworks_schedule", type_="unique")
