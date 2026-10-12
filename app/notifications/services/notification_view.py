from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from app.db.models import Notification


@dataclass(frozen=True, slots=True)
class NotificationView:
    """Application-layer value returned by the notification operations.

    `app/notifications/router.py` maps it to `NotificationResponse`.
    """

    id: UUID
    type: str
    message: str
    details: dict[str, Any] | None
    read: bool
    created_at: datetime

    @classmethod
    def from_model(cls, notification: Notification) -> Self:
        return cls(
            id=notification.id,
            type=notification.type,
            message=notification.message,
            details=notification.details,
            read=notification.read,
            created_at=notification.created_at,
        )
