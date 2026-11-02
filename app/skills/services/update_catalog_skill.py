from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.skills.domain import SkillName
from app.skills.exceptions import CatalogSkillNotFoundError, SkillNameConflictError
from app.skills.schemas import CatalogSkillResponse, CatalogSkillUpdateRequest


def update_catalog_skill(
    session: Session, skill_id: UUID, request: CatalogSkillUpdateRequest
) -> CatalogSkillResponse:
    """Rename, reclassify, inactivate or reactivate a catalog skill.

    Résumés and jobs keep the skill whatever its status, so their compatibility does
    not change. Asking for the status the skill already has is not an error.
    """
    try:
        skill = session.scalar(
            select(Skill).where(Skill.id == skill_id).with_for_update()
        )
        if skill is None:
            raise CatalogSkillNotFoundError
        if request.name is not None:
            name = SkillName.parse(request.name)
            skill.name = name.value
            skill.normalized_name = name.normalized
        if request.type is not None:
            skill.type = request.type
        if request.status is not None:
            skill.is_active = request.status == "active"
        session.flush()
        response = CatalogSkillResponse.of(skill)
        session.commit()
        return response
    except IntegrityError as exc:
        session.rollback()
        raise SkillNameConflictError from exc
    except Exception:
        session.rollback()
        raise
