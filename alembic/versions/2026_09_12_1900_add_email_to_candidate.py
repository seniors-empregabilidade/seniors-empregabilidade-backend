"""Add email column to candidate.

Revision ID: 2026_09_12_1900_add_email_to_candidate
Revises: 210bd68a55ad
Create Date: 2026-09-12
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "2026_09_12_1900_add_email_to_candidate"
down_revision = "210bd68a55ad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the `email` column (unique, non-nullable) to `candidate`."""
    op.add_column(
        "candidate",
        sa.Column("email", sa.String(150), nullable=False, unique=True),
    )
    op.create_unique_constraint("uq_candidate_email", "candidate", ["email"])


def downgrade() -> None:
    """Revert the migration - drop `email` column and its unique constraint."""
    op.drop_constraint("uq_candidate_email", "candidate", type_="unique")
    op.drop_column("candidate", "email")
