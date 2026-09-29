from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job
from app.db.models.enums import JobStatus
from app.jobs.exceptions import (
    JobAlreadyClosedError,
    JobAlreadyOpenError,
    JobNotFoundError,
)
from app.jobs.schemas import UpdateJobStatusRequest
from app.jobs.services.job_record import JobRecord
from app.jobs.services.job_skills import skills_by_job

_TARGET_STATUS = {
    "open": JobStatus.PUBLISHED,
    "closed": JobStatus.CLOSED,
}


def change_job_status(
    job_id: UUID,
    request: UpdateJobStatusRequest,
    *,
    session: Session,
    company_id: UUID,
) -> JobRecord:
    target_status = _TARGET_STATUS[request.status]
    try:
        job = session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.company_id == company_id)
            .with_for_update()
        )
        if job is None:
            raise JobNotFoundError
        if job.status == target_status:
            raise (
                JobAlreadyOpenError()
                if target_status == JobStatus.PUBLISHED
                else JobAlreadyClosedError()
            )

        job.status = target_status
        session.flush()
        record = JobRecord.of(job, skills_by_job([job.id], session=session)[job.id])
        session.commit()
    except Exception:
        session.rollback()
        raise

    return record
