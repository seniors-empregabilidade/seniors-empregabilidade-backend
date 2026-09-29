from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.local_date import to_local_date
from app.db.models import Job
from app.db.models.enums import JobStatus
from app.jobs.exceptions import (
    ClosingDateInThePastError,
    JobAlreadyClosedError,
    JobAlreadyOpenError,
    JobNotFoundError,
    JobStatusChangeNotAllowedError,
)
from app.jobs.schemas import UpdateJobStatusRequest
from app.jobs.services.job_record import JobRecord
from app.jobs.services.job_skills import skills_by_job

# A draft or a job under review has never been open to candidates, so neither
# closing nor opening it belongs to this endpoint.
_CLOSABLE_STATUSES = frozenset(
    {JobStatus.PUBLISHED, JobStatus.PAUSED, JobStatus.EXPIRED}
)
_REOPENABLE_STATUSES = frozenset(
    {JobStatus.CLOSED, JobStatus.PAUSED, JobStatus.EXPIRED, JobStatus.PUBLISHED}
)


def change_job_status(
    job_id: UUID,
    request: UpdateJobStatusRequest,
    *,
    session: Session,
    company_id: UUID,
    now: datetime | None = None,
) -> JobRecord:
    reference_now = now or datetime.now(UTC)
    try:
        job = session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.company_id == company_id)
            .with_for_update()
        )
        if job is None:
            raise JobNotFoundError

        if request.status == "closed":
            _close(job)
        else:
            _reopen(
                job,
                closing_date=request.closing_date or job.closing_date,
                now=reference_now,
            )
        session.flush()
        record = JobRecord.of(job, skills_by_job([job.id], session=session)[job.id])
        session.commit()
    except Exception:
        session.rollback()
        raise

    return record


def _close(job: Job) -> None:
    if job.status == JobStatus.CLOSED:
        raise JobAlreadyClosedError
    if job.status not in _CLOSABLE_STATUSES:
        raise JobStatusChangeNotAllowedError
    job.status = JobStatus.CLOSED


def _reopen(job: Job, *, closing_date: date, now: datetime) -> None:
    # "Open" means what the candidate search shows: published and not past its
    # closing date in the local calendar, the same rule as `is_open_at`.
    today = to_local_date(now)
    if job.status == JobStatus.PUBLISHED and job.closing_date >= today:
        raise JobAlreadyOpenError
    if job.status not in _REOPENABLE_STATUSES:
        raise JobStatusChangeNotAllowedError
    if closing_date < today:
        raise ClosingDateInThePastError

    job.status = JobStatus.PUBLISHED
    job.closing_date = closing_date
    if job.published_at is None:
        job.published_at = now
