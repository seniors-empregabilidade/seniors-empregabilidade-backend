from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.domain.minimum_age import age_on
from app.candidates.domain.resume_completeness import missing_resume_fields
from app.candidates.exceptions import ProfileNotFoundError
from app.candidates.services.records import (
    CertificationRecord,
    EducationRecord,
    ExperienceRecord,
    ProfileRecord,
    certification_record,
    education_record,
    experience_record,
)
from app.db.models.app_user import AppUser
from app.db.models.attached_certificate import AttachedCertificate
from app.db.models.candidate import Candidate
from app.db.models.certification import Certification
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
    certifications: tuple[CertificationRecord, ...] = ()
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
        certifications = tuple(
            certification_record(certification, document)
            for certification, document in session.execute(
                select(Certification, AttachedCertificate)
                .outerjoin(
                    AttachedCertificate,
                    AttachedCertificate.certification_id == Certification.id,
                )
                .where(Certification.resume_id == resume.id)
                .order_by(
                    Certification.issued_date.desc().nulls_last(), Certification.id
                )
            ).tuples()
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
        accepts_automatic_application=candidate.accepts_automatic_application,
        experiences=experiences,
        education=education,
        certifications=certifications,
        skills=skills,
        missing_fields=missing_resume_fields(
            city=candidate.city,
            state=candidate.state,
            summary=resume.summary if resume else None,
            has_experience=bool(experiences),
            has_education=bool(education),
            has_skill=bool(skills),
        ),
    )
