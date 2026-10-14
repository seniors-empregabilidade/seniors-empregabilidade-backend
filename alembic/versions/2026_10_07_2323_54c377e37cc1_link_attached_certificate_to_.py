"""Link attached certificate to certification.

US-07-T01 stores one proof document per certification. ``attached_certificate``
pointed at the resume, so a file could not be matched to the certification it
proves. The row now references ``certification`` and keeps the storage key and
file metadata instead of a URL. No feature uploaded files before this revision,
so existing rows are placeholders without a certification and are removed.

Revision ID: 54c377e37cc1
Revises: 5d2f7a9c1e34
Create Date: 2026-10-07 23:23:45.843107+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "54c377e37cc1"
down_revision: str | Sequence[str] | None = "5d2f7a9c1e34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM attached_certificate")
    op.drop_index(
        op.f("ix_attached_certificate_resume_id"), table_name="attached_certificate"
    )
    op.drop_constraint(
        op.f("fk_attached_certificate_resume_id_resume"),
        "attached_certificate",
        type_="foreignkey",
    )
    op.drop_column("attached_certificate", "file_url")
    op.drop_column("attached_certificate", "resume_id")
    op.add_column(
        "attached_certificate", sa.Column("certification_id", sa.UUID(), nullable=False)
    )
    op.add_column(
        "attached_certificate", sa.Column("object_key", sa.Text(), nullable=False)
    )
    op.add_column(
        "attached_certificate",
        sa.Column("filename", sa.String(length=255), nullable=False),
    )
    op.add_column(
        "attached_certificate",
        sa.Column("content_type", sa.String(length=100), nullable=False),
    )
    op.add_column(
        "attached_certificate", sa.Column("size_bytes", sa.Integer(), nullable=False)
    )
    op.create_foreign_key(
        op.f("fk_attached_certificate_certification_id_certification"),
        "attached_certificate",
        "certification",
        ["certification_id"],
        ["id"],
        ondelete="CASCADE",
        initially="IMMEDIATE",
        deferrable=True,
    )
    op.create_unique_constraint(
        op.f("uq_attached_certificate_certification_id"),
        "attached_certificate",
        ["certification_id"],
    )


def downgrade() -> None:
    op.add_column(
        "attached_certificate", sa.Column("resume_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "attached_certificate", sa.Column("file_url", sa.Text(), nullable=True)
    )
    op.execute(
        """
        UPDATE attached_certificate AS attached
        SET resume_id = certification.resume_id, file_url = attached.object_key
        FROM certification
        WHERE certification.id = attached.certification_id
        """
    )
    op.alter_column("attached_certificate", "resume_id", nullable=False)
    op.alter_column("attached_certificate", "file_url", nullable=False)
    op.drop_constraint(
        op.f("uq_attached_certificate_certification_id"),
        "attached_certificate",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_attached_certificate_certification_id_certification"),
        "attached_certificate",
        type_="foreignkey",
    )
    op.drop_column("attached_certificate", "size_bytes")
    op.drop_column("attached_certificate", "content_type")
    op.drop_column("attached_certificate", "filename")
    op.drop_column("attached_certificate", "object_key")
    op.drop_column("attached_certificate", "certification_id")
    op.create_foreign_key(
        op.f("fk_attached_certificate_resume_id_resume"),
        "attached_certificate",
        "resume",
        ["resume_id"],
        ["id"],
        ondelete="CASCADE",
        initially="IMMEDIATE",
        deferrable=True,
    )
    op.create_index(
        op.f("ix_attached_certificate_resume_id"),
        "attached_certificate",
        ["resume_id"],
        unique=False,
    )
