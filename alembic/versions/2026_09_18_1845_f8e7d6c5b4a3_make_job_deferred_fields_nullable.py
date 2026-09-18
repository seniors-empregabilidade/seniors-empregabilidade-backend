"""Allow job create/publish without deferred catalog fields.

Revision ID: f8e7d6c5b4a3
Revises: d21b63ce9810
"""

import sqlalchemy as sa

from alembic import op

revision = "f8e7d6c5b4a3"
down_revision = "d21b63ce9810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE job ALTER COLUMN work_mode DROP NOT NULL"))
    op.execute(sa.text("ALTER TABLE job ALTER COLUMN closing_date DROP NOT NULL"))


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM job "
            "WHERE work_mode IS NULL OR closing_date IS NULL"
            ")"
        )
    ):
        raise RuntimeError(
            "Cannot restore NOT NULL on job.work_mode/closing_date while null rows exist."
        )
    op.execute(sa.text("ALTER TABLE job ALTER COLUMN closing_date SET NOT NULL"))
    op.execute(sa.text("ALTER TABLE job ALTER COLUMN work_mode SET NOT NULL"))
