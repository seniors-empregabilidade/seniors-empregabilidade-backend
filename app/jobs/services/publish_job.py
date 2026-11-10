from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.local_date import to_local_date
from app.db.models import Job, JobSkill
from app.db.models.enums import JobStatus
from app.jobs.exceptions import ClosingDateInThePastError
from app.jobs.schemas import CreateJobRequest
from app.jobs.services.job_record import JobRecord
from app.skills.services import find_or_create_skills


def publish_job(
    request: CreateJobRequest,
    *,
    session: Session,
    company_id: UUID,
    now: datetime | None = None,
) -> JobRecord:
    published_at = now or datetime.now(UTC)
    if request.closing_date < to_local_date(published_at):
        raise ClosingDateInThePastError

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
        skills = find_or_create_skills(request.skills, session=session)
        session.add(job)
        session.flush()
        session.add_all(JobSkill(job_id=job.id, skill_id=skill.id) for skill in skills)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise

    return JobRecord.of(job, skills)
