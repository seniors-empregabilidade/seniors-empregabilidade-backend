from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import JobSkill, Skill
from app.skills.services import CatalogSkill


def skills_by_job(
    job_ids: Sequence[UUID], *, session: Session
) -> defaultdict[UUID, list[CatalogSkill]]:
    """Each job's catalog skills sorted by name: the typed order is not stored."""
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
