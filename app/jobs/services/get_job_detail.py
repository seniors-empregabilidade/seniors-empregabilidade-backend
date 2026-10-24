from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.db.models import Application, AppUser, Company, Job
from app.db.models.enums import JobStatus, WorkMode
from app.jobs.exceptions import JobNotFoundError
from app.jobs.services.job_skills import skills_by_job
from app.jobs.services.open_job import is_open_at, publishing_company_is_not_blocked
from app.skills.services import CatalogSkill

_NOT_PUBLIC_STATUSES = (JobStatus.DRAFT, JobStatus.UNDER_REVIEW)


@dataclass(frozen=True, slots=True)
class JobDetail:
    id: UUID
    title: str
    description: str
    company_id: UUID
    company_name: str
    skills: list[CatalogSkill]
    work_mode: WorkMode
    location: str | None
    closing_date: date
    status: JobStatus
    published_at: datetime | None
    already_applied: bool
    is_open: bool
    is_expired: bool
    is_applicable: bool


def get_job_detail(
    session: Session,
    *,
    job_id: UUID,
    candidate_id: UUID,
    now: datetime | None = None,
) -> JobDetail:
    """Full data of a job plus the calling candidate's application state.

    A job that is a draft, under review or owned by a `blocked` company account
    answers like a job that does not exist. A paused, expired or closed job, or
    a published one past its closing date, is returned but is not applicable.
    The candidate may already have applied to it, so those stay readable.
    A job is open under the rule of `is_open_at`: `published` and not past its
    closing date in `LOCAL_TIMEZONE`. It is applicable when it is open and the
    candidate has no application to it yet, whatever that application's status,
    because `(candidate_id, job_id)` is unique.
    """
    row = session.execute(
        select(
            Job,
            func.coalesce(Company.trade_name, Company.legal_name).label("company_name"),
            exists()
            .where(
                Application.job_id == Job.id,
                Application.candidate_id == candidate_id,
            )
            .label("already_applied"),
            is_open_at(now or datetime.now(UTC)).label("is_open"),
        )
        .join(Company, Company.id == Job.company_id)
        .join(AppUser, AppUser.id == Company.id)
        .where(
            Job.id == job_id,
            Job.status.not_in(_NOT_PUBLIC_STATUSES),
            publishing_company_is_not_blocked(),
        )
    ).one_or_none()
    if row is None:
        raise JobNotFoundError

    job = row.Job
    is_open = row.is_open
    is_expired = job.status == JobStatus.EXPIRED or (
        job.status == JobStatus.PUBLISHED and not is_open
    )
    return JobDetail(
        id=job.id,
        title=job.title,
        description=job.description,
        company_id=job.company_id,
        company_name=row.company_name,
        skills=skills_by_job([job.id], session=session)[job.id],
        work_mode=job.work_mode,
        location=job.location,
        closing_date=job.closing_date,
        status=job.status,
        published_at=job.published_at,
        already_applied=row.already_applied,
        is_open=is_open,
        is_expired=is_expired,
        is_applicable=is_open and not row.already_applied,
    )
