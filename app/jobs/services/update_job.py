from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill
from app.jobs.exceptions import JobNotFoundError
from app.jobs.schemas import UpdateJobRequest
from app.jobs.services.job_snapshot import JobSnapshot
from app.skills.services import find_or_create_skills


def update_job(
    job_id: UUID,
    request: UpdateJobRequest,
    *,
    session: Session,
    company_id: UUID,
) -> JobSnapshot:
    try:
        job = session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.company_id == company_id)
            .with_for_update()
        )
        if job is None:
            raise JobNotFoundError

        skills = find_or_create_skills(request.skills, session=session)
        job.title = request.title
        job.description = request.description
        session.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
        session.flush()
        session.add_all(JobSkill(job_id=job.id, skill_id=skill.id) for skill in skills)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise

    assert job.published_at is not None, "a persisted job is always published"
    return JobSnapshot(
        id=job.id,
        company_id=job.company_id,
        title=job.title,
        description=job.description,
        skills=skills,
        work_mode=job.work_mode,
        closing_date=job.closing_date,
        status=job.status,
        published_at=job.published_at,
        created_at=job.created_at,
    )
