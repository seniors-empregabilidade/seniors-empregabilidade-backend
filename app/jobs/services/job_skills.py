from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import JobSkill, Skill
from app.skills.services import CatalogSkill


def skills_of_job(session: Session, job_id: UUID) -> list[CatalogSkill]:
    skills = session.scalars(
        select(Skill)
        .join(JobSkill, JobSkill.skill_id == Skill.id)
        .where(JobSkill.job_id == job_id)
        .order_by(Skill.name)
    ).all()
    return [CatalogSkill.of(skill) for skill in skills]


def skills_of_jobs(
    session: Session, job_ids: Sequence[UUID]
) -> dict[UUID, list[CatalogSkill]]:
    rows = session.execute(
        select(JobSkill.job_id, Skill)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(job_ids))
        .order_by(Skill.name)
    ).all()
    skills_by_job: dict[UUID, list[CatalogSkill]] = {}
    for job_id, skill in rows:
        skills_by_job.setdefault(job_id, []).append(CatalogSkill.of(skill))
    return skills_by_job
