from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import DEFAULT_PAGE_SIZE
from app.db.models import Notification
from app.notifications.schemas.notification_list_response import (
    NotificationListResponse,
)
from app.notifications.schemas.notification_response import NotificationResponse


def list_my_notifications(
    session: Session,
    *,
    user_id: UUID,
    unread_only: bool = False,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> NotificationListResponse:
    """Return the caller's notifications, newest first.

    `unread_count` always counts every unread notification of the user,
    regardless of the page or the `unread_only` filter, so the client can
    show a badge from the same response.
    """
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if unread_only:
        statement = statement.where(Notification.read.is_(False))

    notifications = session.scalars(statement).all()
    unread_count = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
    )
    return NotificationListResponse(
        items=[NotificationResponse.from_model(item) for item in notifications],
        unread_count=unread_count or 0,
    )
