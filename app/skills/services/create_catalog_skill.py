from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.skills.domain import SkillName
from app.skills.exceptions import SkillNameConflictError
from app.skills.schemas import CatalogSkillResponse, SkillRequest


def create_catalog_skill(
    session: Session, request: SkillRequest
) -> CatalogSkillResponse:
    """Add an active skill, refusing a name the catalog already has in any status."""
    name = SkillName.parse(request.name)
    try:
        # Two administrators creating the same name at once: one row wins and the
        # other gets the conflict instead of a database error.
        skill = session.scalar(
            insert(Skill)
            .values(name=name.value, normalized_name=name.normalized, type=request.type)
            .on_conflict_do_nothing(index_elements=["normalized_name"])
            .returning(Skill)
        )
        if skill is None:
            raise SkillNameConflictError
        response = CatalogSkillResponse.of(skill)
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
