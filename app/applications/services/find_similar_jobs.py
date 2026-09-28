from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Application, Company, Job, JobSkill
from app.jobs.services import is_open_at

DEFAULT_SIMILARITY_LIMIT = 5


@dataclass(frozen=True, slots=True)
class SimilarJob:
    id: UUID
    title: str
    company_name: str


def find_similar_jobs(
    session: Session,
    *,
    job_id: UUID,
    candidate_id: UUID,
    limit: int = DEFAULT_SIMILARITY_LIMIT,
    now: datetime | None = None,
) -> list[SimilarJob]:
    """Suggest open jobs that share structured skills with `job_id`.

    Ranks other open jobs by how many skills they share with the given job,
    excluding the source job itself and every job the candidate already
    applied to. Openness comes from `app.jobs.services.is_open_at`, the same
    rule the job search uses.
    """
    reference_now = now or datetime.now(UTC)

    shared_skill_count = func.count(JobSkill.skill_id).label("shared_skill_count")
    target_skill_ids = select(JobSkill.skill_id).where(JobSkill.job_id == job_id)
    applied_job_ids = select(Application.job_id).where(
        Application.candidate_id == candidate_id
    )
    company_display_name = func.coalesce(Company.trade_name, Company.legal_name)

    statement = (
        select(Job.id, Job.title, company_display_name.label("company_name"))
        .join(JobSkill, JobSkill.job_id == Job.id)
        .join(Company, Company.id == Job.company_id)
        .where(
            JobSkill.skill_id.in_(target_skill_ids),
            Job.id != job_id,
            Job.id.not_in(applied_job_ids),
            is_open_at(reference_now),
        )
        .group_by(Job.id, Job.title, company_display_name)
        .order_by(shared_skill_count.desc(), Job.id)
        .limit(limit)
    )
    rows = session.execute(statement).all()
    return [
        SimilarJob(id=row.id, title=row.title, company_name=row.company_name)
        for row in rows
    ]
