from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.applications.domain.policies.days_in_process import days_in_process
from app.applications.exceptions import (
    ApplicationAlreadyClosedError,
    ApplicationNotFoundError,
)
from app.applications.schemas.application_summary_response import (
    ApplicationSummaryResponse,
)
from app.db.models import Application, Company, Job
from app.db.models.enums import ApplicationStatus

# Statuses in which a candidate can still leave the process. Every other
# status is already terminal (hired, not_selected, withdrawn or expired).
_ACTIVE_STATUSES = frozenset(
    {
        ApplicationStatus.APPLIED,
        ApplicationStatus.UNDER_REVIEW,
        ApplicationStatus.IN_SELECTION_PROCESS,
    }
)


def withdraw_application(
    session: Session,
    *,
    application_id: UUID,
    candidate_id: UUID,
    now: datetime | None = None,
) -> ApplicationSummaryResponse:
    """Let the owning candidate leave an active selection process.

    This is intentionally irreversible: there is no companion "undo"
    operation, matching the product decision that withdrawing is final. The
    row lock (`SELECT ... FOR UPDATE`) makes the read-check-write sequence
    atomic under concurrency: a second concurrent request blocks until the
    first commits, then observes the already-closed status and receives
    `409 application_already_closed` instead of double-withdrawing.

    Filtering by `candidate_id` in the same query that looks up the
    application means a request for someone else's application finds no row
    at all, so it is indistinguishable from a nonexistent application and
    changes nothing. Both cases raise `ApplicationNotFoundError` (`404`).
    """
    reference_now = now or datetime.now(UTC)
    try:
        application = session.scalar(
            select(Application)
            .where(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            )
            .with_for_update()
        )
        if application is None:
            raise ApplicationNotFoundError
        if application.status not in _ACTIVE_STATUSES:
            raise ApplicationAlreadyClosedError

        application.status = ApplicationStatus.WITHDRAWN
        application.closed_at = reference_now
        session.flush()

        company_display_name = func.coalesce(Company.trade_name, Company.legal_name)
        job = session.execute(
            select(
                Job.title.label("job_title"),
                company_display_name.label("company_name"),
            )
            .join(Company, Company.id == Job.company_id)
            .where(Job.id == application.job_id)
        ).one()

        response = ApplicationSummaryResponse(
            id=application.id,
            job_id=application.job_id,
            job_title=job.job_title,
            company_name=job.company_name,
            submitted_at=application.created_at,
            days_in_process=days_in_process(
                submitted_at=application.created_at,
                closed_at=application.closed_at,
                now=reference_now,
            ),
            status=application.status,
            closed_reason=None,
            similar_jobs=[],
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return response
