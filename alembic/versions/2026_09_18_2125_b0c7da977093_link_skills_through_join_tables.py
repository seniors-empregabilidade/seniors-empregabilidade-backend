"""Link resumes and jobs to skills through join tables.

Follows the wiki data dictionary: resume_skill and job_skill replace
resume.skill_ids and job.desired_skills, so PostgreSQL enforces that every
linked skill exists. Existing links are copied before the old columns are
dropped. The upgrade refuses to run when a stored skill reference points to
no skill, instead of silently discarding it.

Revision ID: b0c7da977093
Revises: 2ca4f0c63705
Create Date: 2026-09-18 21:25:48.012345+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0c7da977093"
down_revision: str | Sequence[str] | None = "2ca4f0c63705"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESUME_SKILL_REFERENCES = """
    SELECT resume.id AS resume_id, linked.skill_id
    FROM resume CROSS JOIN LATERAL unnest(resume.skill_ids) AS linked(skill_id)
"""

JOB_SKILL_REFERENCES = """
    SELECT job.id AS job_id, lower(item ->> 'skill_id') AS skill_id
    FROM job CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(job.desired_skills) = 'array'
        THEN job.desired_skills ELSE '[]'::jsonb END
    ) AS item
"""


def upgrade() -> None:
    _refuse_unknown_skill_references()
    _create_join_table("resume_skill", "resume")
    _create_join_table("job_skill", "job")
    op.execute(f"""
        INSERT INTO resume_skill (resume_id, skill_id)
        SELECT DISTINCT reference.resume_id, reference.skill_id
        FROM ({RESUME_SKILL_REFERENCES}) AS reference
    """)
    op.execute(f"""
        INSERT INTO job_skill (job_id, skill_id)
        SELECT DISTINCT reference.job_id, skill.id
        FROM ({JOB_SKILL_REFERENCES}) AS reference
        JOIN skill ON skill.id::text = reference.skill_id
    """)
    op.drop_column("job", "desired_skills")
    op.drop_column("resume", "skill_ids")


def downgrade() -> None:
    op.add_column(
        "resume",
        sa.Column(
            "skill_ids",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "job",
        sa.Column(
            "desired_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute("""
        UPDATE resume SET skill_ids = linked.skill_ids
        FROM (
            SELECT resume_id, array_agg(skill_id ORDER BY skill_id) AS skill_ids
            FROM resume_skill GROUP BY resume_id
        ) AS linked
        WHERE resume.id = linked.resume_id
    """)
    # The old JSON shape was never defined beyond skill_id, so nothing else is rebuilt.
    op.execute("""
        UPDATE job SET desired_skills = linked.desired_skills
        FROM (
            SELECT job_id, jsonb_agg(
                jsonb_build_object('skill_id', skill_id::text) ORDER BY skill_id
            ) AS desired_skills
            FROM job_skill GROUP BY job_id
        ) AS linked
        WHERE job.id = linked.job_id
    """)
    op.drop_table("job_skill")
    op.drop_table("resume_skill")


def _refuse_unknown_skill_references() -> None:
    unknown = op.get_bind().scalar(
        sa.text(f"""
            SELECT
                (SELECT count(*) FROM ({RESUME_SKILL_REFERENCES}) AS reference
                 WHERE NOT EXISTS (
                     SELECT 1 FROM skill WHERE skill.id = reference.skill_id
                 ))
              + (SELECT count(*) FROM ({JOB_SKILL_REFERENCES}) AS reference
                 WHERE NOT EXISTS (
                     SELECT 1 FROM skill WHERE skill.id::text = reference.skill_id
                 ))
        """)
    )
    if unknown:
        raise RuntimeError(
            f"{unknown} stored skill references point to no skill; fix them first."
        )


def _create_join_table(table_name: str, owner: str) -> None:
    op.create_table(
        table_name,
        sa.Column(f"{owner}_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            [f"{owner}_id"],
            [f"{owner}.id"],
            name=op.f(f"fk_{table_name}_{owner}_id_{owner}"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f(f"fk_{table_name}_skill_id_skill"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
        sa.UniqueConstraint(
            f"{owner}_id",
            "skill_id",
            name=op.f(f"uq_{table_name}_{owner}_id_skill_id"),
        ),
    )
