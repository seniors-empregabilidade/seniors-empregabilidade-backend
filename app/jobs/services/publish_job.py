from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, Skill
from app.db.models.enums import JobStatus
from app.jobs.exceptions import UnknownSkillsError
from app.jobs.schemas import CreateJobRequest, JobResponse


def publish_job(
    request: CreateJobRequest,
    *,
    session: Session,
    company_id: UUID,
    now: datetime | None = None,
) -> JobResponse:
    published_at = now or datetime.now(UTC)
    skill_ids = _unique_skill_ids(request.skill_ids)
    _ensure_skills_exist(session, skill_ids)

    job = Job(
        company_id=company_id,
        title=request.title,
        description=request.description,
        status=JobStatus.PUBLISHED,
        published_at=published_at,
        desired_skills=[
            {"skill_id": str(skill_id), "required": True} for skill_id in skill_ids
        ],
    )
    try:
        session.add(job)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise

    return JobResponse(
        id=job.id,
        company_id=job.company_id,
        title=job.title,
        description=job.description,
        skill_ids=skill_ids,
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
