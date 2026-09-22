import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.skills.domain import MAX_SKILL_NAME_LENGTH, normalize_skill_name
from app.skills.services.catalog_skill import CatalogSkill


def search_skills(
    *, session: Session, search: str | None = None, limit: int
) -> list[CatalogSkill]:
    """List catalog skills that contain the searched text, ignoring case and accents.

    A blank search lists the catalog. A search that no stored name could contain,
    because it outgrows the column once normalized or carries a control character,
    finds nothing instead of reaching the database.
    """
    statement = select(Skill).order_by(Skill.name).limit(limit)
    term = normalize_skill_name(search) if search is not None else ""
    if term:
        if not _could_be_stored(term):
            return []
        statement = statement.where(
            Skill.normalized_name.contains(term, autoescape=True)
        )

    return [CatalogSkill.of(skill) for skill in session.scalars(statement)]


def _could_be_stored(term: str) -> bool:
    return len(term) <= MAX_SKILL_NAME_LENGTH and not any(
        unicodedata.category(character) == "Cc" for character in term
    )
