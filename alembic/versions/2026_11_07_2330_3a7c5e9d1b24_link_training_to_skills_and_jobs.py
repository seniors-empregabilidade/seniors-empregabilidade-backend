"""Link trainings to the skills they teach and the jobs they prepare for.

US-22-T01 turns the existing ``training`` table into the course catalog. A
course teaches many skills and may point to many jobs, so each relation gets its
own join table. Both cascade from either side: deleting a course, a skill or a
job removes only the link, never the other record.

Revision ID: 3a7c5e9d1b24
Revises: 1f1f595d6227
Create Date: 2026-11-07 23:30:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a7c5e9d1b24"
down_revision: str | Sequence[str] | None = "1f1f595d6227"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_skill",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("training_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_training_skill_skill_id_skill"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["training_id"],
            ["training.id"],
            name=op.f("fk_training_skill_training_id_training"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_skill")),
        sa.UniqueConstraint(
            "training_id",
            "skill_id",
            name=op.f("uq_training_skill_training_id_skill_id"),
        ),
    )
    op.create_index(
        op.f("ix_training_skill_skill_id"), "training_skill", ["skill_id"], unique=False
    )
    op.create_table(
        "training_job",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("training_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
            name=op.f("fk_training_job_job_id_job"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["training_id"],
            ["training.id"],
            name=op.f("fk_training_job_training_id_training"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_job")),
        sa.UniqueConstraint(
            "training_id",
            "job_id",
            name=op.f("uq_training_job_training_id_job_id"),
        ),
    )
    op.create_index(
        op.f("ix_training_job_job_id"), "training_job", ["job_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_training_job_job_id"), table_name="training_job")
    op.drop_table("training_job")
    op.drop_index(op.f("ix_training_skill_skill_id"), table_name="training_skill")
    op.drop_table("training_skill")
