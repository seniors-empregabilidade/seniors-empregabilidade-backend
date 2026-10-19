from uuid import UUID

from sqlalchemy import func, literal, select, tuple_
from sqlalchemy.orm import Session

from app.core.pagination import DEFAULT_PAGE_SIZE
from app.db.models import Notification
from app.notifications.domain.notification_cursor import (
    InvalidNotificationCursor,
    NotificationCursor,
)
from app.notifications.exceptions import InvalidNotificationCursorError
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
    cursor: str | None = None,
) -> NotificationListResponse:
    """Return one page of the caller's notifications, newest first.

    Pages are keyed on `(created_at, id)`, served by the
    `ix_notification_user_id_created_at_id` index. `unread_count` always counts
    every unread notification of the user, regardless of the page or the
    `unread_only` filter, so the client can show a badge from the same response.
    """
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        # One extra row tells whether another page exists.
        .limit(limit + 1)
    )
    if unread_only:
        statement = statement.where(Notification.read.is_(False))
    if cursor is not None:
        try:
            position = NotificationCursor.decode(cursor)
        except InvalidNotificationCursor as exc:
            raise InvalidNotificationCursorError from exc
        statement = statement.where(
            tuple_(Notification.created_at, Notification.id)
            < tuple_(
                literal(position.created_at, Notification.created_at.type),
                literal(position.id, Notification.id.type),
            )
        )

    rows = session.scalars(statement).all()
    page = rows[:limit]
    next_cursor = (
        NotificationCursor(created_at=page[-1].created_at, id=page[-1].id).encode()
        if len(rows) > limit
        else None
    )
    unread_count = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
    )
    return NotificationListResponse(
        items=[NotificationResponse.from_model(item) for item in page],
        unread_count=unread_count or 0,
        next_cursor=next_cursor,
    )
