from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.skills.domain import InvalidSkillNameError, SkillName
from app.skills.services.catalog_skill import CatalogSkill


def search_skills(
    *, session: Session, search: str | None = None, limit: int
) -> list[CatalogSkill]:
    """List catalog skills that contain the searched text, ignoring case and accents."""
    statement = select(Skill).order_by(Skill.name).limit(limit)
    term = _comparable(search)
    if term:
        statement = statement.where(
            Skill.normalized_name.contains(term, autoescape=True)
        )

    return [CatalogSkill.of(skill) for skill in session.scalars(statement)]


def _comparable(search: str | None) -> str | None:
    if search is None:
        return None
    try:
        return SkillName.parse(search).normalized
    except InvalidSkillNameError:
        return None
