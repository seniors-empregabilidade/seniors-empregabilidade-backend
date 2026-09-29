from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Application, Job
from app.jobs.services.job_record import JobRecord
from app.jobs.services.job_skills import skills_by_job
from app.jobs.services.job_summary import JobSummary


def list_company_jobs(*, session: Session, company_id: UUID) -> list[JobSummary]:
    """List every job the company created, newest first.

    Each job carries its catalog skills, sorted by name, and the number of
    applications it received, whatever their status.
    """
    jobs = session.scalars(
        select(Job)
        .where(Job.company_id == company_id)
        .order_by(Job.created_at.desc(), Job.id)
    ).all()
    job_ids = [job.id for job in jobs]
    skills = skills_by_job(job_ids, session=session)
    applications = _application_counts(job_ids, session=session)
    return [
        JobSummary(JobRecord.of(job, skills[job.id]), applications.get(job.id, 0))
        for job in jobs
    ]


def _application_counts(
    job_ids: Sequence[UUID], *, session: Session
) -> dict[UUID, int]:
    if not job_ids:
        return {}

    rows = session.execute(
        select(Application.job_id, func.count(Application.id))
        .where(Application.job_id.in_(job_ids))
        .group_by(Application.job_id)
    )
    return dict(rows.tuples().all())
