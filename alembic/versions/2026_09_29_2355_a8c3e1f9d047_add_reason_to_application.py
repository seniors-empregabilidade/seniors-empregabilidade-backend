"""Add reason to application.

US-21-T01 allows a company to record the reason for not selecting a candidate.
The reason is stored on the ``application`` row and shown to the candidate
(US-13). It is nullable so that existing rows and applications closed with
other statuses are unaffected.

Revision ID: a8c3e1f9d047
Revises: fc5ef2d18be7
Create Date: 2026-09-29 23:55:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8c3e1f9d047"
down_revision: str | Sequence[str] | None = "fc5ef2d18be7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "application",
        sa.Column("reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application", "reason")
