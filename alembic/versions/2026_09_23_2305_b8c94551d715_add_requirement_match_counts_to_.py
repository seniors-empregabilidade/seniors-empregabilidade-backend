"""Add requirement match counts to application.

US-12-T01 registers "matches X of Y requirements" the moment a candidate applies,
so the number shown later does not drift if the job's required skills or the
candidate's resume skills change afterward. `application.match_score` already
exists as a single 0-100 percentage, but nothing populates it yet and it cannot
losslessly represent X and Y (many (X, Y) pairs share the same percentage), so
this task leaves it untouched and adds two explicit counts instead.

Revision ID: b8c94551d715
Revises: fc5ef2d18be7
Create Date: 2026-09-23 23:05:51.069537+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c94551d715"
down_revision: str | Sequence[str] | None = "fc5ef2d18be7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "application",
        sa.Column("matched_requirements", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "application", sa.Column("total_requirements", sa.SmallInteger(), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_application_requirements_range"),
        "application",
        "matched_requirements IS NULL OR (total_requirements IS NOT NULL AND "
        "matched_requirements BETWEEN 0 AND total_requirements)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_application_requirements_range"), "application", type_="check"
    )
    op.drop_column("application", "total_requirements")
    op.drop_column("application", "matched_requirements")
