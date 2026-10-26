import logging
from uuid import UUID

from app.applications.services.generate_automatic_applications import (
    generate_automatic_applications_for_job,
)
from app.db.session import get_session_factory

_logger = logging.getLogger("app.applications")


def apply_automatically_to_new_job(job_id: UUID, threshold_percent: int) -> None:
    """Evaluate a just-published job in its own session, after the response.

    The company already got its `201`: a failure here is logged and never reaches
    the request. The daily round only looks at later accounts, so a failure is not
    retried for professionals registered before the job; fix the cause and publish
    again, or re-run the evaluation by hand.
    """
    try:
        with get_session_factory()() as session:
            generate_automatic_applications_for_job(
                session, job_id=job_id, threshold_percent=threshold_percent
            )
    except Exception as exc:
        _logger.error(
            "automatic_applications_failed",
            extra={
                "event": "automatic_applications_failed",
                "trigger": "job",
                "exception_type": type(exc).__name__,
            },
        )
