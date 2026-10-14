"""Seed the baseline soft skills of the catalog.

US-06-T01 asks for a standardized catalog that starts with at least "Ética" and
"Trabalho em grupo", so a professional choosing skills finds them in every
environment. ``scripts/seed.py`` only runs locally and in tests, so the entries are
inserted here, where every deployment applies them.

A company may have typed one of these names before this revision ran, in which
case the catalog already holds that entry and the insert keeps it. A downgrade
leaves both skills in place because the database cannot distinguish an inserted
baseline skill from a pre-existing company entry, and deleting a skill could
remove links from résumés or jobs. The normalized names are written out instead
of computed by the application so that this migration keeps describing what it did.

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
    # Catalog entries are shared user data. Their origin cannot be recovered.
    pass
