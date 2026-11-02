from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.db.models.enums import SkillType
from app.skills.domain import normalize_skill_name
from app.skills.schemas import (
    CatalogSkillListResponse,
    CatalogSkillResponse,
    SkillStatus,
)
from app.skills.services.search_skills import could_be_stored


def list_catalog_skills(
    session: Session,
    *,
    search: str | None,
    skill_type: SkillType | None,
    status: SkillStatus | None,
    limit: int,
    offset: int,
) -> CatalogSkillListResponse:
    """List the whole catalog, inactive skills included, for its administration."""
    conditions: list[ColumnElement[bool]] = []
    term = normalize_skill_name(search) if search is not None else ""
    if term:
        if not could_be_stored(term):
            return CatalogSkillListResponse(items=[], total=0)
        conditions.append(Skill.normalized_name.contains(term, autoescape=True))
    if skill_type is not None:
        conditions.append(Skill.type == skill_type)
    if status is not None:
        conditions.append(Skill.is_active.is_(status == "active"))

    total = session.scalar(select(func.count()).select_from(Skill).where(*conditions))
    skills = session.scalars(
        select(Skill)
        .where(*conditions)
        .order_by(Skill.name, Skill.id)
        .limit(limit)
        .offset(offset)
    )
    return CatalogSkillListResponse(
        items=[CatalogSkillResponse.of(skill) for skill in skills], total=total or 0
    )
