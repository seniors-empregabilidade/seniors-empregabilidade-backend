import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, EmailDelivery, EmailDeliveryStatus, Notification
from app.db.models.enums import UserType
from app.db.session import get_session_factory
from app.email.email_sender import EmailSendError
from app.notifications.domain.notification_type import NotificationType
from app.notifications.services.dispatch_pending_emails import (
    dispatch_pending_emails,
)
from app.notifications.services.notify_user import notify_user

pytestmark = pytest.mark.integration

APP_URL = "https://app.example.invalid"
NOW = datetime(2026, 10, 19, 21, 0, tzinfo=UTC)


@dataclass
class FakeEmailSender:
    failure_code: str | None = None
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    def send(self, *, to: str, subject: str, body: str) -> None:
        if self.failure_code is not None:
            raise EmailSendError(self.failure_code)
        self.sent.append((to, subject, body))


def queue_email(
    session: Session,
    email: str,
    notification_type: NotificationType = NotificationType.APPLICATION_RECEIVED,
) -> tuple[UUID, EmailDelivery]:
    user = AppUser(email=email, identity_subject=None, user_type=UserType.COMPANY)
    session.add(user)
    session.flush()
    notify_user(
        session, user_id=user.id, type=notification_type, message="Synthetic message"
    )
    session.flush()
    delivery = session.scalars(
        select(EmailDelivery)
        .join(Notification, Notification.id == EmailDelivery.notification_id)
        .where(Notification.user_id == user.id)
    ).one()
    delivery.next_attempt_at = NOW - timedelta(seconds=1)
    session.commit()
    return user.id, delivery


def dispatch(
    session: Session, sender: FakeEmailSender, *, max_attempts: int = 5, **kwargs: int
) -> int:
    return dispatch_pending_emails(
        session,
        sender=sender,
        app_url=APP_URL,
        max_attempts=max_attempts,
        now=NOW,
        **kwargs,
    )


def test_due_email_is_sent_to_the_users_current_address(
    database_session: Session,
) -> None:
    _, delivery = queue_email(database_session, "dispatch-a@synthetic.example.invalid")
    sender = FakeEmailSender()

    assert dispatch(database_session, sender) == 1

    database_session.refresh(delivery)
    assert delivery.status == EmailDeliveryStatus.SENT
    assert delivery.sent_at == NOW
    assert delivery.attempts == 1
    assert delivery.last_error is None
    assert len(sender.sent) == 1
    to, subject, body = sender.sent[0]
    assert to == "dispatch-a@synthetic.example.invalid"
    assert subject == "Nova candidatura em uma vaga sua"
    assert APP_URL in body
    assert "Synthetic message" not in body


def test_failure_keeps_the_email_pending_with_a_later_retry(
    database_session: Session,
) -> None:
    _, delivery = queue_email(database_session, "dispatch-b@synthetic.example.invalid")

    dispatch(database_session, FakeEmailSender(failure_code="Throttling"))

    database_session.refresh(delivery)
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.attempts == 1
    assert delivery.last_error == "Throttling"
    assert delivery.next_attempt_at == NOW + timedelta(minutes=1)
    assert delivery.sent_at is None


def test_failed_email_never_touches_the_in_app_notification(
    database_session: Session,
) -> None:
    user_id, _ = queue_email(database_session, "dispatch-c@synthetic.example.invalid")

    dispatch(database_session, FakeEmailSender(failure_code="MessageRejected"))

    notification = database_session.scalars(
        select(Notification).where(Notification.user_id == user_id)
    ).one()
    assert notification.message == "Synthetic message"
    assert notification.read is False


def test_last_allowed_failure_marks_the_email_failed(
    database_session: Session,
) -> None:
    _, delivery = queue_email(database_session, "dispatch-d@synthetic.example.invalid")
    delivery.attempts = 4
    database_session.commit()

    dispatch(database_session, FakeEmailSender(failure_code="MessageRejected"))

    database_session.refresh(delivery)
    assert delivery.status == EmailDeliveryStatus.FAILED
    assert delivery.attempts == 5
    assert delivery.last_error == "MessageRejected"


def test_email_waiting_for_its_retry_is_not_sent_early(
    database_session: Session,
) -> None:
    _, delivery = queue_email(database_session, "dispatch-e@synthetic.example.invalid")
    delivery.next_attempt_at = NOW + timedelta(minutes=5)
    database_session.commit()
    sender = FakeEmailSender()

    dispatch(database_session, sender)

    database_session.refresh(delivery)
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.attempts == 0
    assert sender.sent == []


@pytest.mark.parametrize(
    "status", [EmailDeliveryStatus.SENT, EmailDeliveryStatus.FAILED]
)
def test_finished_email_is_never_sent_again(
    database_session: Session, status: EmailDeliveryStatus
) -> None:
    _, delivery = queue_email(database_session, "dispatch-f@synthetic.example.invalid")
    delivery.status = status
    database_session.commit()
    sender = FakeEmailSender()

    dispatch(database_session, sender)

    assert sender.sent == []


def test_delivery_for_an_in_app_only_event_fails_without_sending(
    database_session: Session,
) -> None:
    user_id, _ = queue_email(database_session, "dispatch-g@synthetic.example.invalid")
    notification = database_session.scalars(
        select(Notification).where(Notification.user_id == user_id)
    ).one()
    notification.type = NotificationType.COMPANY_REGISTRATION_REJECTED.value
    database_session.commit()
    sender = FakeEmailSender()

    dispatch(database_session, sender)

    delivery = database_session.scalars(
        select(EmailDelivery).where(EmailDelivery.notification_id == notification.id)
    ).one()
    assert delivery.status == EmailDeliveryStatus.FAILED
    assert delivery.last_error == "unsupported_notification_type"
    assert delivery.attempts == 0
    assert sender.sent == []


def test_batch_size_caps_one_round(database_session: Session) -> None:
    for position in range(3):
        queue_email(
            database_session, f"dispatch-batch-{position}@synthetic.example.invalid"
        )
    sender = FakeEmailSender()

    assert dispatch(database_session, sender, batch_size=2) == 2
    assert len(sender.sent) == 2
    assert dispatch(database_session, sender, batch_size=2) == 1
    assert dispatch(database_session, sender, batch_size=2) == 0


def test_email_claimed_by_another_dispatcher_is_skipped() -> None:
    if os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1":
        pytest.skip("requires RUN_DATABASE_INTEGRATION_TESTS=1 and PostgreSQL")
    factory = get_session_factory()
    with factory() as setup:
        user_id, delivery = queue_email(
            setup, "dispatch-locked@synthetic.example.invalid"
        )
    try:
        with factory() as holder, factory() as competitor:
            # The holder plays a dispatcher that is still sending this e-mail.
            holder.execute(
                select(EmailDelivery)
                .where(EmailDelivery.id == delivery.id)
                .with_for_update()
            ).one()
            sender = FakeEmailSender()

            assert dispatch(competitor, sender) == 0
            assert sender.sent == []

            holder.rollback()
            assert dispatch(competitor, sender) == 1
            assert len(sender.sent) == 1
    finally:
        with factory.begin() as cleanup:
            cleanup.execute(delete(AppUser).where(AppUser.id == user_id))
