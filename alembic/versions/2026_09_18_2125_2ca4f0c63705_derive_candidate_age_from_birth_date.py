"""Derive candidate age from birth date instead of storing it.

A stored age becomes stale on the candidate's next birthday. The wiki data
dictionary keeps only birth_date, which already enforces the minimum age.

Revision ID: 2ca4f0c63705
Revises: d21b63ce9810
Create Date: 2026-09-18 21:25:23.868372+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2ca4f0c63705"
down_revision: str | Sequence[str] | None = "d21b63ce9810"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_candidate_age_value"), "candidate", type_="check")
    op.drop_column("candidate", "age")


def downgrade() -> None:
    op.add_column("candidate", sa.Column("age", sa.SmallInteger(), nullable=True))
    op.execute(
        "UPDATE candidate SET age = date_part('year', age(birth_date))::smallint"
    )
    op.create_check_constraint(
        op.f("ck_candidate_age_value"), "candidate", "age IS NULL OR age >= 45"
    )
