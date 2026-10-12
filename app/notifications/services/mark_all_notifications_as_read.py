from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import Notification


def mark_all_notifications_as_read(session: Session, *, user_id: UUID) -> None:
    try:
        session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read.is_(False))
            .values(read=True)
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
