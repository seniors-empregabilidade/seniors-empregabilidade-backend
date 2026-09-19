from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.applications.schemas.similar_job_response import SimilarJobResponse
from app.db.models import Application, Company, Job, JobSkill
from app.db.models.enums import JobStatus

DEFAULT_SIMILARITY_LIMIT = 5


def find_similar_jobs(
    session: Session,
    *,
    job_id: UUID,
    candidate_id: UUID,
    limit: int = DEFAULT_SIMILARITY_LIMIT,
) -> list[SimilarJobResponse]:
    """Suggest published jobs that share structured skills with `job_id`.

    Provisional US-17-T01/US-10-T01 stand-in: there is no shared skill-matching
    engine yet, so this reuses the `job_skill` join table directly and ranks
    other published jobs by how many skills they share with the given job
    (simple set intersection, most shared skills first). It excludes the
    source job itself and every job the candidate already applied to, and
    caps the result to a small number of suggestions. Replace this function's
    body with the shared engine once US-17-T01/US-10-T01 exist; the call site
    in `list_my_applications` does not need to change.
    """
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
            Job.status == JobStatus.PUBLISHED,
        )
        .group_by(Job.id, Job.title, company_display_name)
        .order_by(shared_skill_count.desc(), Job.id)
        .limit(limit)
    )
    rows = session.execute(statement).all()
    return [
        SimilarJobResponse(id=row.id, title=row.title, company_name=row.company_name)
        for row in rows
    ]
