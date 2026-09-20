from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.applications.domain.policies.days_in_process import days_in_process
from app.applications.services.application_summary import ApplicationSummary
from app.applications.services.find_similar_jobs import find_similar_jobs
from app.db.models import Application, Company, Job
from app.db.models.enums import ApplicationStatus

# Suggestions are shown only for applications closed without a selection
# decision. Active applications and applications the candidate withdrew are
# excluded on purpose (see docs/APPLICATIONS.md).
_STATUSES_WITH_SUGGESTIONS = frozenset({ApplicationStatus.NOT_SELECTED})


def list_my_applications(
    session: Session,
    *,
    candidate_id: UUID,
    company_name: str | None = None,
    now: datetime | None = None,
) -> list[ApplicationSummary]:
    reference_now = now or datetime.now(UTC)
    company_display_name = func.coalesce(Company.trade_name, Company.legal_name)

    statement = (
        select(
            Application.id,
            Application.job_id,
            Job.title.label("job_title"),
            company_display_name.label("company_name"),
            Application.created_at.label("submitted_at"),
            Application.status,
            Application.closed_at,
        )
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Job.company_id)
        .where(Application.candidate_id == candidate_id)
        .order_by(Application.created_at.desc(), Application.id)
    )
    if company_name:
        statement = statement.where(company_display_name.ilike(f"%{company_name}%"))

    rows = session.execute(statement).all()

    summaries = []
    for row in rows:
        similar_jobs = (
            find_similar_jobs(
                session,
                job_id=row.job_id,
                candidate_id=candidate_id,
                now=reference_now,
            )
            if row.status in _STATUSES_WITH_SUGGESTIONS
            else []
        )
        summaries.append(
            ApplicationSummary(
                id=row.id,
                job_id=row.job_id,
                job_title=row.job_title,
                company_name=row.company_name,
                submitted_at=row.submitted_at,
                days_in_process=days_in_process(
                    submitted_at=row.submitted_at,
                    closed_at=row.closed_at,
                    now=reference_now,
                ),
                status=row.status,
                similar_jobs=similar_jobs,
            )
        )
    return summaries
