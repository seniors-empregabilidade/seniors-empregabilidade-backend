"""Turn the automatic application preference on by default.

Revision ID: c4a1d7e9b3f2
Revises: 9e4b6c2d8a17
Create Date: 2026-10-25 12:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a1d7e9b3f2"
down_revision: str | Sequence[str] | None = "9e4b6c2d8a17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "candidate",
        "accepts_automatic_application",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
        existing_nullable=False,
    )
    # No endpoint ever set the column, so every existing `false` is the old
    # default and not a choice. Professionals opt out through the preference task (T05).
    op.execute("UPDATE candidate SET accepts_automatic_application = true")


def downgrade() -> None:
    # The backfill is not reversed: it cannot tell the old default from an
    # opt-out made after this revision.
    op.alter_column(
        "candidate",
        "accepts_automatic_application",
        existing_type=sa.Boolean(),
        server_default=sa.text("false"),
        existing_nullable=False,
    )
