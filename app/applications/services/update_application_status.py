from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.exceptions import (
    ApplicationAlreadyClosedError,
    ApplicationNotFoundError,
    ApplicationStatusTransitionNotAllowedError,
)
from app.applications.schemas.update_application_status_request import (
    UpdateApplicationStatusRequest,
)
from app.applications.services.application_action_result import ApplicationActionResult
from app.db.models import Application, Job
from app.db.models.enums import ApplicationStatus

# Terminal statuses: the company cannot move an application away from these.
_TERMINAL_STATUSES = frozenset(
    {
        ApplicationStatus.HIRED,
        ApplicationStatus.NOT_SELECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.EXPIRED,
    }
)

# Valid transitions the company may trigger.
# Key: current status → Value: set of allowed target statuses.
_ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.APPLIED: frozenset({ApplicationStatus.UNDER_REVIEW}),
    ApplicationStatus.UNDER_REVIEW: frozenset(
        {
            ApplicationStatus.IN_SELECTION_PROCESS,
            ApplicationStatus.NOT_SELECTED,
        }
    ),
    ApplicationStatus.IN_SELECTION_PROCESS: frozenset(
        {
            ApplicationStatus.HIRED,
            ApplicationStatus.NOT_SELECTED,
        }
    ),
}

_STATUS_MAP: dict[str, ApplicationStatus] = {
    "under_review": ApplicationStatus.UNDER_REVIEW,
    "in_selection_process": ApplicationStatus.IN_SELECTION_PROCESS,
    "hired": ApplicationStatus.HIRED,
    "not_selected": ApplicationStatus.NOT_SELECTED,
}


def update_application_status(
    session: Session,
    *,
    application_id: UUID,
    company_id: UUID,
    request: UpdateApplicationStatusRequest,
    now: datetime | None = None,
) -> ApplicationActionResult:
    """Company-side update of a candidate's application status.

    Only the company that owns the job can act on its applications. An
    application that belongs to a different company's job is returned as 404,
    indistinguishable from a non-existent application, to avoid leaking
    existence.

    Status transitions follow ``_ALLOWED_TRANSITIONS``. Attempting a
    transition not listed there raises ``ApplicationStatusTransitionNotAllowedError``
    (409). Applications in a terminal status raise
    ``ApplicationAlreadyClosedError`` (409).

    When the target status is ``not_selected``, the ``reason`` field (present
    in the request) is persisted in the ``reason`` column so it can be
    displayed to the candidate (US-13).
    """
    reference_now = now or datetime.now(UTC)
    target_status = _STATUS_MAP[request.status]

    try:
        row = session.execute(
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(
                Application.id == application_id,
                Job.company_id == company_id,
            )
            .with_for_update()
        ).one_or_none()

        if row is None:
            raise ApplicationNotFoundError

        application, _job = row

        if application.status in _TERMINAL_STATUSES:
            raise ApplicationAlreadyClosedError

        allowed = _ALLOWED_TRANSITIONS.get(application.status, frozenset())
        if target_status not in allowed:
            raise ApplicationStatusTransitionNotAllowedError

        application.status = target_status
        application.updated_at = reference_now

        if target_status in (ApplicationStatus.HIRED, ApplicationStatus.NOT_SELECTED):
            application.closed_at = reference_now

        if target_status == ApplicationStatus.NOT_SELECTED and request.reason:
            application.reason = request.reason

        session.flush()
        result = ApplicationActionResult(
            application_id=application.id,
            job_id=application.job_id,
            candidate_id=application.candidate_id,
            status=application.status,
            updated_at=application.updated_at,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return result
