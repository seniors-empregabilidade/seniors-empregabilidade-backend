"""Identify catalog skills by a normalized name.

A skill typed as "Gestão de equipes", "gestao de equipes" or " GESTÃO  DE EQUIPES "
is the same catalog entry, so the uniqueness moves from the (name, type) pair to
the normalized name. The normalization is repeated here instead of imported from
the application so that this migration keeps describing what it did.

Revision ID: fc5ef2d18be7
Revises: 1c381f6d0f82
Create Date: 2026-09-19 22:27:41.508930+00:00

"""

import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc5ef2d18be7"
down_revision: str | Sequence[str] | None = "1c381f6d0f82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Normalizing can make a name longer ("ß" becomes "ss"), so a name that fits
# skill.name does not always fit this column.
_NORMALIZED_NAME_LENGTH = 100


def upgrade() -> None:
    _refuse_names_that_outgrow_the_normalized_column()
    op.add_column(
        "skill",
        sa.Column("normalized_name", sa.String(_NORMALIZED_NAME_LENGTH), nullable=True),
    )
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


def _refuse_names_that_outgrow_the_normalized_column() -> None:
    names = op.get_bind().scalars(sa.text("SELECT name FROM skill ORDER BY name"))
    too_long = [
        name for name in names if len(_normalized(name)) > _NORMALIZED_NAME_LENGTH
    ]
    if too_long:
        raise RuntimeError(
            f"These skills would exceed {_NORMALIZED_NAME_LENGTH} characters once "
            "normalized; shorten them first: " + "; ".join(too_long)
        )


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
    # Accents, accents typed on their own and invisible characters are dropped,
    # then repeated spaces are collapsed.
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    kept = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) not in {"Mn", "Sk", "Cf"}
    )
    return " ".join(kept.split())
