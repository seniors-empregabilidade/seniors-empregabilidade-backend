from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Company, Job, JobSkill, Resume, ResumeSkill, Skill
from app.db.models.enums import WorkMode
from app.jobs.domain.policies.days_since_published import days_since_published
from app.jobs.domain.policies.skill_match import match_skills
from app.jobs.services.open_job import is_open_at
from app.skills.services import CatalogSkill


@dataclass(frozen=True, slots=True)
class FoundJob:
    id: UUID
    title: str
    company_name: str
    location: str | None
    work_mode: WorkMode
    salary_max: Decimal | None
    published_at: datetime | None
    days_since_published: int | None
    matched_skill_count: int
    required_skill_count: int
    missing_skills: list[CatalogSkill]


def search_jobs(
    session: Session,
    *,
    candidate_id: UUID,
    search: str | None,
    limit: int,
    offset: int,
    now: datetime | None = None,
) -> list[FoundJob]:
    """List open jobs whose title contains `search`, most compatible first.

    A blank search lists every open job. A search with a NUL character, which
    no stored title can contain, finds nothing instead of reaching the database.
    """
    reference_now = now or datetime.now(UTC)
    term = search.strip() if search else ""
    if "\x00" in term:
        return []

    candidate_skills = frozenset(
        session.scalars(
            select(ResumeSkill.skill_id)
            .join(Resume, Resume.id == ResumeSkill.resume_id)
            .where(Resume.candidate_id == candidate_id)
        )
    )
    matched_skill_count = func.count(JobSkill.skill_id).filter(
        JobSkill.skill_id.in_(candidate_skills)
    )
    company_display_name = func.coalesce(Company.trade_name, Company.legal_name)
    statement = (
        select(
            Job.id,
            Job.title,
            company_display_name.label("company_name"),
            Job.location,
            Job.work_mode,
            Job.salary_max,
            Job.published_at,
        )
        .join(Company, Company.id == Job.company_id)
        .outerjoin(JobSkill, JobSkill.job_id == Job.id)
        .where(is_open_at(reference_now))
        .group_by(Job.id, Company.id)
        .order_by(
            matched_skill_count.desc(),
            Job.published_at.desc().nulls_last(),
            Job.id,
        )
        .limit(limit)
        .offset(offset)
    )
    if term:
        statement = statement.where(Job.title.icontains(term, autoescape=True))

    rows = session.execute(statement).all()
    if not rows:
        return []

    skills_by_job = _required_skills(session, job_ids=[row.id for row in rows])

    found = []
    for row in rows:
        required = skills_by_job[row.id]
        match = match_skills(
            candidate_skill_ids=candidate_skills,
            required_skill_ids={skill.id for skill in required},
        )
        found.append(
            FoundJob(
                id=row.id,
                title=row.title,
                company_name=row.company_name,
                location=row.location,
                work_mode=row.work_mode,
                salary_max=row.salary_max,
                published_at=row.published_at,
                days_since_published=(
                    days_since_published(
                        published_at=row.published_at, now=reference_now
                    )
                    if row.published_at is not None
                    else None
                ),
                matched_skill_count=match.matched_count,
                required_skill_count=match.required_count,
                missing_skills=[
                    skill for skill in required if skill.id in match.missing_skill_ids
                ],
            )
        )
    return found


def _required_skills(
    session: Session, *, job_ids: list[UUID]
) -> defaultdict[UUID, list[CatalogSkill]]:
    skills_by_job: defaultdict[UUID, list[CatalogSkill]] = defaultdict(list)
    rows = session.execute(
        select(JobSkill.job_id, Skill)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(job_ids))
        .order_by(Skill.name, Skill.id)
    )
    for job_id, skill in rows.tuples():
        skills_by_job[job_id].append(CatalogSkill.of(skill))
    return skills_by_job
