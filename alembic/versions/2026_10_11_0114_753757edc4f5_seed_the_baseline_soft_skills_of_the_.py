"""Seed the baseline soft skills of the catalog.

US-06-T01 asks for a standardized catalog that starts with at least "Ética" and
"Trabalho em grupo", so a professional choosing skills finds them in every
environment. ``scripts/seed.py`` only runs locally and in tests, so the entries are
inserted here, where every deployment applies them.

A company may have typed one of these names before this revision ran, in which
case the catalog already holds that entry and the insert keeps it. The normalized
names are written out instead of computed by the application so that this
migration keeps describing what it did.

Revision ID: 753757edc4f5
Revises: b8c94551d715
Create Date: 2026-10-11 01:14:56.553722+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "753757edc4f5"
down_revision: str | Sequence[str] | None = "b8c94551d715"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASELINE_SKILLS = (
    {"name": "Ética", "normalized_name": "etica"},
    {"name": "Trabalho em grupo", "normalized_name": "trabalho em grupo"},
)
NORMALIZED_NAMES = [skill["normalized_name"] for skill in BASELINE_SKILLS]


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO skill (name, normalized_name, type) "
            "VALUES (:name, :normalized_name, 'soft') "
            "ON CONFLICT (normalized_name) DO NOTHING"
        ),
        list(BASELINE_SKILLS),
    )


def downgrade() -> None:
    connection = op.get_bind()
    _refuse_skills_still_in_use(connection)
    connection.execute(
        sa.text("DELETE FROM skill WHERE normalized_name IN :names").bindparams(
            sa.bindparam("names", expanding=True)
        ),
        {"names": NORMALIZED_NAMES},
    )


def _refuse_skills_still_in_use(connection: sa.Connection) -> None:
    # Deleting a skill cascades to the résumés and jobs that chose it, which would
    # silently erase what people saved. Unlinking them is a decision for a person.
    in_use = (
        connection.execute(
            sa.text(
                "SELECT skill.name FROM skill "
                "WHERE skill.normalized_name IN :names "
                "AND (EXISTS (SELECT 1 FROM resume_skill "
                "WHERE resume_skill.skill_id = skill.id) "
                "OR EXISTS (SELECT 1 FROM job_skill "
                "WHERE job_skill.skill_id = skill.id)) "
                "ORDER BY skill.name"
            ).bindparams(sa.bindparam("names", expanding=True)),
            {"names": NORMALIZED_NAMES},
        )
        .scalars()
        .all()
    )
    if in_use:
        raise RuntimeError(
            "These skills are chosen by résumés or jobs; unlink them before "
            "downgrading: " + ", ".join(in_use)
        )
