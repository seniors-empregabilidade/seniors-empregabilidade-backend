from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import ProfileNotFoundError
from app.candidates.schemas.profile import (
    EducationResponse,
    ExperienceResponse,
    ProfessionalProfileResponse,
)
from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.education import Education
from app.db.models.experience import Experience
from app.db.models.resume import Resume
from app.db.models.resume_skill import ResumeSkill
from app.db.models.skill import Skill


def calculate_age(birth_date: date, today: date | None = None) -> int:
    reference = today or date.today()
    had_birthday = (reference.month, reference.day) >= (
        birth_date.month,
        birth_date.day,
    )
    return reference.year - birth_date.year - (0 if had_birthday else 1)


def get_profile(user_id: UUID, *, session: Session) -> ProfessionalProfileResponse:
    candidate = session.get(Candidate, user_id)
    if candidate is None:
        raise ProfileNotFoundError()

    user = session.get(AppUser, user_id)
    if user is None:
        raise ProfileNotFoundError()

    resume = session.scalar(select(Resume).where(Resume.candidate_id == user_id))

    experiences: list[ExperienceResponse] = []
    education: list[EducationResponse] = []
    skills: list[str] = []

    if resume is not None:
        experiences = [
            ExperienceResponse(
                id=row.id,
                role=row.role,
                company_name=row.company_name,
                start_date=row.start_date,
                end_date=row.end_date,
                description=row.description,
            )
            for row in session.scalars(
                select(Experience)
                .where(Experience.resume_id == resume.id)
                .order_by(Experience.start_date.desc())
            )
        ]

        education = [
            EducationResponse(
                id=row.id,
                institution=row.institution,
                degree=row.degree,
                field=row.field,
                start_date=row.start_date,
                end_date=row.end_date,
            )
            for row in session.scalars(
                select(Education).where(Education.resume_id == resume.id)
            )
        ]

        skills = list(
            session.scalars(
                select(Skill.name)
                .join(ResumeSkill, ResumeSkill.skill_id == Skill.id)
                .where(ResumeSkill.resume_id == resume.id)
                .order_by(Skill.name)
            )
        )

    return ProfessionalProfileResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        age=calculate_age(candidate.birth_date),
        email=user.email,
        phone=candidate.phone,
        city=candidate.city,
        state=candidate.state,
        photo_url=None,
        summary=resume.summary if resume else None,
        experiences=experiences,
        education=education,
        skills=skills,
    )
