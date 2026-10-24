"""Record administrator guidance for professionals.

Revision ID: 2ee06058c78d
Revises: 9b83337775e5
Create Date: 2026-10-19 22:58:31.143724+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2ee06058c78d"
down_revision: str | Sequence[str] | None = "9b83337775e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_guidance",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("administrator_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(note)) BETWEEN 1 AND 2000",
            name=op.f("ck_resume_guidance_note_length"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("fk_resume_guidance_candidate_id_candidate"),
            ondelete="CASCADE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["administrator_id"],
            ["administrator.id"],
            name=op.f("fk_resume_guidance_administrator_id_administrator"),
            ondelete="RESTRICT",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_guidance")),
    )
    op.create_index(
        "ix_resume_guidance_candidate_id_created_at_id",
        "resume_guidance",
        ["candidate_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resume_guidance_candidate_id_created_at_id", table_name="resume_guidance"
    )
    op.drop_table("resume_guidance")
