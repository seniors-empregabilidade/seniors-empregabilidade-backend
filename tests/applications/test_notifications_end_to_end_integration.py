"""End-to-end integration for the notification → e-mail seam (US-26-T04).

These tests exercise the full chain a producer event triggers: an HTTP call
creates the in-app notification and a ``pending`` ``EmailDelivery`` in one
transaction, and a later ``dispatch_pending_emails`` run turns that delivery
into ``sent`` with a deliberately generic body. The per-half behaviour is
covered elsewhere (``tests/applications`` for the producers,
``tests/notifications/services/test_dispatch_pending_emails.py`` for the
dispatcher); here we only prove the two halves meet.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    AppUser,
    EmailDelivery,
    EmailDeliveryStatus,
    Job,
    Notification,
)
from app.db.session import get_session_factory
from app.email.email_sender import EmailSendError
from app.notifications.services.dispatch_pending_emails import (
    dispatch_pending_emails,
)
from tests.applications.conftest import (
    SUBMIT_TOKEN,
    SubmissionScenario,
    authorization,
)
from tests.applications.test_update_application_status_router_integration import (
    COMPANY_TOKEN,
    UpdateStatusScenario,
    auth,
    status_path,
    update_status_client,
    update_status_identity_provider,
    update_status_scenario,
)

pytestmark = pytest.mark.integration

APP_URL = "https://app.example.invalid"

# Re-export the imported fixtures so pytest resolves them in this module.
__all__ = [
    "update_status_client",
    "update_status_identity_provider",
    "update_status_scenario",
]


@dataclass
class FakeEmailSender:
    """Collects what it would have sent instead of reaching a provider."""

    failure_code: str | None = None
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    def send(self, *, to: str, subject: str, body: str) -> None:
        if self.failure_code is not None:
            raise EmailSendError(self.failure_code)
        self.sent.append((to, subject, body))


def test_application_notifies_and_sends_email_end_to_end(
    applications_client: TestClient, submission_scenario: SubmissionScenario
) -> None:
    response = applications_client.post(
        "/api/v1/applications",
        json={"job_id": str(submission_scenario.job_open_id)},
        headers=authorization(SUBMIT_TOKEN),
    )
    assert response.status_code == 201

    sender = FakeEmailSender()
    now = datetime.now(UTC)
    with get_session_factory()() as session:
        attempted = dispatch_pending_emails(
            session, sender=sender, app_url=APP_URL, max_attempts=5, now=now
        )

    assert attempted == 1
    assert len(sender.sent) == 1
    to, subject, body = sender.sent[0]

    with get_session_factory()() as session:
        job = session.get(Job, submission_scenario.job_open_id)
        assert job is not None
        recipient_user = session.get(AppUser, job.company_id)
        assert recipient_user is not None
        notification = session.scalars(
            select(Notification).where(Notification.user_id == job.company_id)
        ).one()
        delivery = session.scalars(
            select(EmailDelivery).where(
                EmailDelivery.notification_id == notification.id
            )
        ).one()
        assert delivery.status == EmailDeliveryStatus.SENT
        assert delivery.sent_at == now
        notification_message = notification.message

    assert to == recipient_user.email
    assert subject == "Nova candidatura em uma vaga sua"
    assert APP_URL in body
    assert notification_message not in body
    assert "Submission Open Role" not in body


def test_status_change_notifies_and_sends_email_end_to_end(
    update_status_client: TestClient,
    database_session: Session,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.under_review_application_id),
        json={"status": "in_selection_process"},
        headers=auth(COMPANY_TOKEN),
    )
    assert response.status_code == 200

    application = database_session.get(
        Application, update_status_scenario.under_review_application_id
    )
    assert application is not None
    candidate_id: UUID = application.candidate_id
    recipient_user = database_session.get(AppUser, candidate_id)
    assert recipient_user is not None

    sender = FakeEmailSender()
    now = datetime.now(UTC)
    attempted = dispatch_pending_emails(
        database_session, sender=sender, app_url=APP_URL, max_attempts=5, now=now
    )

    assert attempted == 1
    assert len(sender.sent) == 1
    to, subject, body = sender.sent[0]

    notification = database_session.scalars(
        select(Notification).where(Notification.user_id == candidate_id)
    ).one()
    delivery = database_session.scalars(
        select(EmailDelivery).where(EmailDelivery.notification_id == notification.id)
    ).one()
    assert delivery.status == EmailDeliveryStatus.SENT
    assert delivery.sent_at == now

    assert to == recipient_user.email
    assert subject == "Atualização em uma candidatura sua"
    assert APP_URL in body
    assert notification.message not in body
    assert "em processo seletivo" not in body
