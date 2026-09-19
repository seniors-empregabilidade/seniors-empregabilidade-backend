"""Add closed_at to application.

US-13-T01 needs the exact moment an application left the active pipeline to
compute "days in process" deterministically. `updated_at` has no `onupdate`
trigger in this schema, so it cannot stand in for a closing timestamp. Any
future transition into a terminal status (hired, not_selected, withdrawn,
expired) should set this column; today only the candidate withdrawal
endpoint does so.

Revision ID: 1c381f6d0f82
Revises: b0c7da977093
Create Date: 2026-09-19 22:08:00.861450+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c381f6d0f82"
down_revision: str | Sequence[str] | None = "b0c7da977093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "application",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application", "closed_at")
