"""Add the business contact of a company, apart from its login e-mail.

US-30-T01 lets a company edit its contact e-mail and phone without touching
``corporate_email``, which is the e-mail used to log in. Both columns are
nullable: existing companies keep ``null`` and the API reads the login e-mail
as the contact e-mail until the profile is edited.

Revision ID: 1f1f595d6227
Revises: 21585dd80658
Create Date: 2026-11-03 16:53:04.136040+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1f1f595d6227"
down_revision: str | Sequence[str] | None = "21585dd80658"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "company", sa.Column("contact_email", sa.String(length=150), nullable=True)
    )
    op.add_column(
        "company", sa.Column("contact_phone", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("company", "contact_phone")
    op.drop_column("company", "contact_email")
