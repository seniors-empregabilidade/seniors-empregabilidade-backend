from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill
from app.db.models.enums import JobStatus, WorkMode
from app.jobs.exceptions import ClosingDateInThePastError
from app.jobs.schemas import CreateJobRequest
from app.skills.services import CatalogSkill, find_or_create_skills


@dataclass(frozen=True, slots=True)
class PublishedJob:
    id: UUID
    company_id: UUID
    title: str
    description: str
    skills: list[CatalogSkill]
    work_mode: WorkMode
    closing_date: date
    status: JobStatus
    published_at: datetime
    created_at: datetime


def publish_job(
    request: CreateJobRequest,
    *,
    session: Session,
    company_id: UUID,
    today: date | None = None,
    now: datetime | None = None,
) -> PublishedJob:
    reference_date = today or date.today()
    published_at = now or datetime.now(UTC)
    if request.closing_date < reference_date:
        raise ClosingDateInThePastError

    skills = find_or_create_skills(request.skills, session=session)

    job = Job(
        company_id=company_id,
        title=request.title,
        description=request.description,
        work_mode=request.work_mode,
        closing_date=request.closing_date,
        status=JobStatus.PUBLISHED,
        published_at=published_at,
    )
    try:
        session.add(job)
        session.flush()
        session.add_all(JobSkill(job_id=job.id, skill_id=skill.id) for skill in skills)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise

    return PublishedJob(
        id=job.id,
        company_id=job.company_id,
        title=job.title,
        description=job.description,
        skills=skills,
        work_mode=job.work_mode,
        closing_date=job.closing_date,
        status=job.status,
        published_at=published_at,
        created_at=job.created_at,
    )
