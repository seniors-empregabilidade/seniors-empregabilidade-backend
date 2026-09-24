from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Application, Job
from app.db.models.enums import JobStatus, WorkMode
from app.jobs.services.job_skills import skills_of_jobs
from app.skills.services import CatalogSkill


@dataclass(frozen=True, slots=True)
class JobSummary:
    id: UUID
    title: str
    description: str
    skills: list[CatalogSkill]
    work_mode: WorkMode
    closing_date: date
    status: JobStatus
    published_at: datetime
    created_at: datetime
    application_count: int


def list_my_jobs(session: Session, *, company_id: UUID) -> list[JobSummary]:
    jobs = (
        session.execute(
            select(Job)
            .where(Job.company_id == company_id)
            .order_by(Job.created_at.desc(), Job.id)
        )
        .scalars()
        .all()
    )
    if not jobs:
        return []

    job_ids = [job.id for job in jobs]
    counts: dict[UUID, int] = {}
    for job_id, count in session.execute(
        select(Application.job_id, func.count(Application.id))
        .where(Application.job_id.in_(job_ids))
        .group_by(Application.job_id)
    ):
        counts[job_id] = count
    skills_by_job = skills_of_jobs(session, job_ids)

    summaries = []
    for job in jobs:
        assert job.published_at is not None, "a persisted job is always published"
        summaries.append(
            JobSummary(
                id=job.id,
                title=job.title,
                description=job.description,
                skills=skills_by_job.get(job.id, []),
                work_mode=job.work_mode,
                closing_date=job.closing_date,
                status=job.status,
                published_at=job.published_at,
                created_at=job.created_at,
                application_count=counts.get(job.id, 0),
            )
        )
    return summaries
