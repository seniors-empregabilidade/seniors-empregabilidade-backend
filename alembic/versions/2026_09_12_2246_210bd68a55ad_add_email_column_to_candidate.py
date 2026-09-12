"""add email column to candidate"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "210bd68a55ad"
down_revision = "d21b63ce9810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the `email` column (unique, non-nullable) to `candidate` table."""
    op.add_column(
        "candidate",
        sa.Column("email", sa.String(150), nullable=False, unique=True),
    )
    op.create_unique_constraint("uq_candidate_email", "candidate", ["email"])


def downgrade() -> None:
    """Remove the `email` column and its unique constraint from `candidate`."""
    op.drop_constraint("uq_candidate_email", "candidate", type_="unique")
    op.drop_column("candidate", "email")
