from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import SkillAlreadyAddedError, SkillNotFoundError
from app.candidates.schemas.skill_link import SkillLinkRequest
from app.candidates.services.resumes import get_or_create_resume
from app.db.models.resume import Resume
from app.db.models.resume_skill import ResumeSkill
from app.db.models.skill import Skill
from app.skills.services import CatalogSkill


def add_skill(
    user_id: UUID, request: SkillLinkRequest, *, session: Session
) -> CatalogSkill:
    try:
        skill = session.get(Skill, request.skill_id)
        if skill is None:
            raise SkillNotFoundError()

        resume = get_or_create_resume(user_id, session)
        already_added = session.scalar(
            select(ResumeSkill).where(
                ResumeSkill.resume_id == resume.id,
                ResumeSkill.skill_id == skill.id,
            )
        )
        if already_added is not None:
            raise SkillAlreadyAddedError()

        session.add(ResumeSkill(resume_id=resume.id, skill_id=skill.id))
        session.flush()
        catalog_skill = CatalogSkill.of(skill)
        session.commit()
        return catalog_skill
    except Exception:
        session.rollback()
        raise


def remove_skill(user_id: UUID, skill_id: UUID, *, session: Session) -> None:
    try:
        link = session.scalar(
            select(ResumeSkill)
            .join(Resume, Resume.id == ResumeSkill.resume_id)
            .where(Resume.candidate_id == user_id, ResumeSkill.skill_id == skill_id)
        )
        if link is None:
            raise SkillNotFoundError()

        session.delete(link)
        session.commit()
    except Exception:
        session.rollback()
        raise
