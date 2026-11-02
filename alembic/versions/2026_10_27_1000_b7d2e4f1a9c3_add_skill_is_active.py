"""Add is_active to skill.

US-06-T05 lets an administrator inactivate a catalog skill. An inactive skill
leaves the public catalog but stays on the résumés and jobs that already use it,
so it is a flag instead of a deletion.

Revision ID: b7d2e4f1a9c3
Revises: 9e4b6c2d8a17
Create Date: 2026-10-27 10:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2e4f1a9c3"
down_revision: str | Sequence[str] | None = "9e4b6c2d8a17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "skill",
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("skill", "is_active")
