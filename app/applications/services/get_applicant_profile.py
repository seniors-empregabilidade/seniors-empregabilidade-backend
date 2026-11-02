from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.exceptions import ApplicationNotFoundError
from app.candidates.services import get_profile
from app.candidates.services.records import (
    CertificationRecord,
    EducationRecord,
    ExperienceRecord,
)
from app.db.models import Application, Job
from app.skills.services import CatalogSkill


@dataclass(frozen=True, slots=True)
class ApplicantDetail:
    application_id: UUID
    candidate_id: UUID
    full_name: str
    city: str | None
    state: str | None
    summary: str | None
    experiences: tuple[ExperienceRecord, ...]
    education: tuple[EducationRecord, ...]
    certifications: tuple[CertificationRecord, ...]
    skills: tuple[CatalogSkill, ...]


def get_applicant_profile(
    session: Session, *, application_id: UUID, company_id: UUID
) -> ApplicantDetail:
    """Expose a résumé only to the company that owns its application job."""
    candidate_id = session.scalar(
        select(Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Application.id == application_id, Job.company_id == company_id)
    )
    if candidate_id is None:
        raise ApplicationNotFoundError

    profile = get_profile(candidate_id, session=session)
    return ApplicantDetail(
        application_id=application_id,
        candidate_id=candidate_id,
        full_name=profile.full_name,
        city=profile.city,
        state=profile.state,
        summary=profile.summary,
        experiences=profile.experiences,
        education=profile.education,
        certifications=profile.certifications,
        skills=profile.skills,
    )
