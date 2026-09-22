from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.domain.minimum_age import age_on
from app.candidates.exceptions import ProfileNotFoundError
from app.candidates.services.records import (
    EducationRecord,
    ExperienceRecord,
    ProfileRecord,
    education_record,
    experience_record,
)
from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.education import Education
from app.db.models.experience import Experience
from app.db.models.resume import Resume
from app.db.models.resume_skill import ResumeSkill
from app.db.models.skill import Skill
from app.skills.services import CatalogSkill


def get_profile(user_id: UUID, *, session: Session) -> ProfileRecord:
    candidate = session.get(Candidate, user_id)
    if candidate is None:
        raise ProfileNotFoundError()

    user = session.get(AppUser, user_id)
    if user is None:
        raise ProfileNotFoundError()

    resume = session.scalar(select(Resume).where(Resume.candidate_id == user_id))

    experiences: tuple[ExperienceRecord, ...] = ()
    education: tuple[EducationRecord, ...] = ()
    skills: tuple[CatalogSkill, ...] = ()

    if resume is not None:
        experiences = tuple(
            experience_record(row)
            for row in session.scalars(
                select(Experience)
                .where(Experience.resume_id == resume.id)
                .order_by(Experience.start_date.desc(), Experience.id)
            )
        )
        education = tuple(
            education_record(row)
            for row in session.scalars(
                select(Education)
                .where(Education.resume_id == resume.id)
                .order_by(Education.start_date.desc().nulls_last(), Education.id)
            )
        )
        skills = tuple(
            CatalogSkill.of(row)
            for row in session.scalars(
                select(Skill)
                .join(ResumeSkill, ResumeSkill.skill_id == Skill.id)
                .where(ResumeSkill.resume_id == resume.id)
                .order_by(Skill.name)
            )
        )

    return ProfileRecord(
        id=candidate.id,
        full_name=candidate.full_name,
        age=age_on(candidate.birth_date, date.today()),
        email=user.email,
        phone=candidate.phone,
        city=candidate.city,
        state=candidate.state,
        summary=resume.summary if resume else None,
        experiences=experiences,
        education=education,
        skills=skills,
    )
