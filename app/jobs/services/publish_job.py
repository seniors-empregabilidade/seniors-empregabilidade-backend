from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill, Skill
from app.db.models.enums import JobStatus, WorkMode
from app.jobs.exceptions import ClosingDateInThePastError, UnknownSkillsError
from app.jobs.schemas import CreateJobRequest


@dataclass(frozen=True, slots=True)
class PublishedJob:
    id: UUID
    company_id: UUID
    title: str
    description: str
    skill_ids: list[UUID]
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

    skill_ids = _unique_skill_ids(request.skill_ids)
    _ensure_skills_exist(session, skill_ids)

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
        session.add_all(
            JobSkill(job_id=job.id, skill_id=skill_id) for skill_id in skill_ids
        )
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
        skill_ids=skill_ids,
        work_mode=job.work_mode,
        closing_date=job.closing_date,
        status=job.status,
        published_at=published_at,
        created_at=job.created_at,
    )


def _unique_skill_ids(skill_ids: list[UUID]) -> list[UUID]:
    unique: list[UUID] = []
    seen: set[UUID] = set()
    for skill_id in skill_ids:
        if skill_id in seen:
            continue
        seen.add(skill_id)
        unique.append(skill_id)
    return unique


def _ensure_skills_exist(session: Session, skill_ids: list[UUID]) -> None:
    found = set(session.scalars(select(Skill.id).where(Skill.id.in_(skill_ids))).all())
    if found != set(skill_ids):
        raise UnknownSkillsError
