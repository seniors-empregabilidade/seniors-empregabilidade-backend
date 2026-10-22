import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, EmailDelivery, EmailDeliveryStatus, Notification
from app.email.email_sender import EmailSender, EmailSendError
from app.notifications.domain.email_retry_policy import gives_up, retry_delay
from app.notifications.domain.notification_email import (
    notification_email,
    sends_email,
)
from app.notifications.domain.notification_type import NotificationType

_logger = logging.getLogger("app.email")

_UNSUPPORTED_TYPE = "unsupported_notification_type"


def dispatch_pending_emails(
    session: Session,
    *,
    sender: EmailSender,
    app_url: str,
    max_attempts: int,
    batch_size: int = 20,
    now: datetime | None = None,
) -> int:
    """Send due e-mails one at a time and return how many were attempted.

    Each delivery is claimed with `FOR UPDATE SKIP LOCKED` and committed on its
    own, so a second dispatcher never sends the same row and a crash repeats at
    most the message being sent. A failure stays `pending` with a growing wait
    until `max_attempts`, then becomes `failed`; the notification itself is
    never touched.
    """
    attempted = 0
    while attempted < batch_size:
        reference_now = now or datetime.now(UTC)
        try:
            claimed = session.execute(
                select(EmailDelivery, Notification.type, AppUser.email)
                .join(Notification, Notification.id == EmailDelivery.notification_id)
                .join(AppUser, AppUser.id == Notification.user_id)
                .where(
                    EmailDelivery.status == EmailDeliveryStatus.PENDING,
                    EmailDelivery.next_attempt_at <= reference_now,
                )
                .order_by(EmailDelivery.next_attempt_at, EmailDelivery.id)
                .limit(1)
                .with_for_update(of=EmailDelivery, skip_locked=True)
            ).one_or_none()
            if claimed is None:
                session.commit()
                return attempted

            delivery, notification_type, recipient = claimed
            _send(
                delivery,
                notification_type=notification_type,
                recipient=recipient,
                sender=sender,
                app_url=app_url,
                max_attempts=max_attempts,
                now=reference_now,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        attempted += 1
    return attempted


def _send(
    delivery: EmailDelivery,
    *,
    notification_type: str,
    recipient: str,
    sender: EmailSender,
    app_url: str,
    max_attempts: int,
    now: datetime,
) -> None:
    known_types = {member.value for member in NotificationType}
    if notification_type not in known_types or not sends_email(
        NotificationType(notification_type)
    ):
        # Nothing to retry: no attempt would ever produce a message.
        delivery.status = EmailDeliveryStatus.FAILED
        delivery.last_error = _UNSUPPORTED_TYPE
        return

    email = notification_email(NotificationType(notification_type), app_url=app_url)
    delivery.attempts += 1
    try:
        sender.send(to=recipient, subject=email.subject, body=email.body)
    except EmailSendError as exc:
        delivery.last_error = exc.code[:100]
        if gives_up(delivery.attempts, max_attempts=max_attempts):
            delivery.status = EmailDeliveryStatus.FAILED
        else:
            delivery.next_attempt_at = now + retry_delay(delivery.attempts)
        _logger.warning(
            "email_delivery_failed",
            extra={"event": "email_delivery_failed", "exception_type": exc.code},
        )
        return

    delivery.status = EmailDeliveryStatus.SENT
    delivery.sent_at = now
    delivery.last_error = None
