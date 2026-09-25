from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill, Skill
from app.jobs.services.job_record import JobRecord
from app.skills.services import CatalogSkill


def list_company_jobs(*, session: Session, company_id: UUID) -> list[JobRecord]:
    """List every job the company created, newest first, with its catalog skills.

    A job's skills are sorted by name: the order they were typed in is not stored.
    """
    jobs = session.scalars(
        select(Job)
        .where(Job.company_id == company_id)
        .order_by(Job.created_at.desc(), Job.id)
    ).all()
    skills = _skills_by_job([job.id for job in jobs], session=session)
    return [JobRecord.of(job, skills[job.id]) for job in jobs]


def _skills_by_job(
    job_ids: Sequence[UUID], *, session: Session
) -> defaultdict[UUID, list[CatalogSkill]]:
    skills: defaultdict[UUID, list[CatalogSkill]] = defaultdict(list)
    if not job_ids:
        return skills

    rows = session.execute(
        select(JobSkill.job_id, Skill)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(job_ids))
        .order_by(Skill.name, Skill.id)
    )
    for job_id, skill in rows.tuples():
        skills[job_id].append(CatalogSkill.of(skill))
    return skills
