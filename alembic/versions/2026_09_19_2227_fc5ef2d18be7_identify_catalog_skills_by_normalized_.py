"""Identify catalog skills by a normalized name.

A skill typed as "Gestão de equipes", "gestao de equipes" or " GESTÃO  DE EQUIPES "
is the same catalog entry, so the uniqueness moves from the (name, type) pair to
the normalized name. The normalization is repeated here instead of imported from
the application so that this migration keeps describing what it did.

Revision ID: fc5ef2d18be7
Revises: b0c7da977093
Create Date: 2026-09-19 22:27:41.508930+00:00

"""

import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc5ef2d18be7"
down_revision: str | Sequence[str] | None = "b0c7da977093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("skill", sa.Column("normalized_name", sa.String(100), nullable=True))
    _fill_normalized_names()
    _refuse_names_that_became_duplicates()
    op.alter_column("skill", "normalized_name", nullable=False)
    op.create_unique_constraint(
        op.f("uq_skill_normalized_name"), "skill", ["normalized_name"]
    )
    op.drop_constraint(op.f("uq_skill_name_type"), "skill", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(op.f("uq_skill_name_type"), "skill", ["name", "type"])
    op.drop_constraint(op.f("uq_skill_normalized_name"), "skill", type_="unique")
    op.drop_column("skill", "normalized_name")


def _fill_normalized_names() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, name FROM skill")).all()
    for skill_id, name in rows:
        connection.execute(
            sa.text("UPDATE skill SET normalized_name = :value WHERE id = :id"),
            {"value": _normalized(name), "id": skill_id},
        )


def _refuse_names_that_became_duplicates() -> None:
    duplicates = op.get_bind().scalars(
        sa.text("""
            SELECT string_agg(name, ', ' ORDER BY name)
            FROM skill GROUP BY normalized_name HAVING count(*) > 1
        """)
    )
    conflicts = list(duplicates)
    if conflicts:
        raise RuntimeError(
            "These skills would become the same catalog entry; merge them first: "
            + "; ".join(conflicts)
        )


def _normalized(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", " ".join(name.split()).casefold())
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
