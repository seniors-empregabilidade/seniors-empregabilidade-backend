from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import EmailDelivery, Notification
from app.notifications.domain.notification_email import sends_email
from app.notifications.domain.notification_type import NotificationType


def notify_user(
    session: Session,
    *,
    user_id: UUID,
    type: NotificationType,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Record an in-app notification inside the caller's transaction.

    This is the single entry point for event producers (company review,
    applications, contact requests, ...). It never commits: the notification
    is persisted only if the business change that caused it is committed,
    and disappears with it on rollback.

    `details` is returned to the notified user as-is. Keep it to identifiers
    the client needs to build a link (for example `application_id`); never
    put personal data, documents or credentials in it.

    Events listed in `notification_email` also queue an e-mail copy in the
    same transaction. It is only sent after the commit, by the e-mail
    dispatcher, so a provider failure never undoes the in-app notification.
    """
    notification = Notification(
        user_id=user_id,
        type=type.value,
        message=message,
        details=details,
    )
    session.add(notification)
    if sends_email(type):
        session.add(EmailDelivery(notification=notification))
