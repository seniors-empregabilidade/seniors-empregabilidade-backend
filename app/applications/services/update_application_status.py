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
from app.notifications.domain.notification_type import NotificationType
from app.notifications.services.notify_user import notify_user

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

# Statuses a company may set, each with the wording shown to the candidate
# in the in-app notification. One table keeps both in step: a status added
# here cannot be accepted without a label.
_COMPANY_STATUSES: dict[str, tuple[ApplicationStatus, str]] = {
    "under_review": (ApplicationStatus.UNDER_REVIEW, "em análise"),
    "in_selection_process": (
        ApplicationStatus.IN_SELECTION_PROCESS,
        "em processo seletivo",
    ),
    "hired": (ApplicationStatus.HIRED, "contratado"),
    "not_selected": (ApplicationStatus.NOT_SELECTED, "não selecionado"),
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
    target_status, status_label = _COMPANY_STATUSES[request.status]

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

        application, job = row

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
        # The rejection reason is deliberately left out: the candidate reads
        # it from their application list, not from the notification.
        notify_user(
            session,
            user_id=application.candidate_id,
            type=NotificationType.APPLICATION_STATUS_CHANGED,
            message=(
                f'Sua candidatura para a vaga "{job.title}" mudou para: {status_label}.'
            ),
            details={
                "application_id": str(application.id),
                "job_id": str(job.id),
                "status": target_status.value,
            },
        )
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
