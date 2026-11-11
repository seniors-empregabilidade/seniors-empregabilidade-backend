"""add profile photo columns

Add five nullable photo columns to both ``candidate`` and ``company``.
All five share the same naming convention: ``photo_object_key``,
``photo_filename``, ``photo_content_type``, ``photo_size_bytes``,
``photo_uploaded_at``. A non-NULL ``photo_object_key`` signals that the
entity has a profile photo stored; the remaining four columns carry its
metadata.

Revision ID: 9466fd3b08cf
Revises: 3a7c5e9d1b24
Create Date: 2026-11-11 23:33:29.247846+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9466fd3b08cf"
down_revision: str | Sequence[str] | None = "3a7c5e9d1b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candidate", sa.Column("photo_object_key", sa.Text(), nullable=True))
    op.add_column(
        "candidate", sa.Column("photo_filename", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "candidate",
        sa.Column("photo_content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "candidate", sa.Column("photo_size_bytes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "candidate",
        sa.Column("photo_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("company", sa.Column("photo_object_key", sa.Text(), nullable=True))
    op.add_column(
        "company", sa.Column("photo_filename", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "company", sa.Column("photo_content_type", sa.String(length=100), nullable=True)
    )
    op.add_column("company", sa.Column("photo_size_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "company",
        sa.Column("photo_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company", "photo_uploaded_at")
    op.drop_column("company", "photo_size_bytes")
    op.drop_column("company", "photo_content_type")
    op.drop_column("company", "photo_filename")
    op.drop_column("company", "photo_object_key")
    op.drop_column("candidate", "photo_uploaded_at")
    op.drop_column("candidate", "photo_size_bytes")
    op.drop_column("candidate", "photo_content_type")
    op.drop_column("candidate", "photo_filename")
    op.drop_column("candidate", "photo_object_key")
