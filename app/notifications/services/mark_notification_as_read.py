from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import Notification
from app.notifications.exceptions import NotificationNotFoundError
from app.notifications.schemas.notification_response import NotificationResponse


def mark_notification_as_read(
    session: Session, *, notification_id: UUID, user_id: UUID
) -> NotificationResponse:
    """Mark one of the caller's notifications as read.

    Idempotent: marking an already-read notification succeeds again. Filtering
    by `user_id` in the same statement makes another user's notification
    indistinguishable from a nonexistent one (`404`) and leaves it untouched.
    """
    try:
        notification = session.scalar(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .values(read=True)
            .returning(Notification)
        )
        if notification is None:
            raise NotificationNotFoundError
        response = NotificationResponse.from_model(notification)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return response
