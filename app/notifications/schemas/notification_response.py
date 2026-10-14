from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import Notification


class NotificationResponse(BaseModel):
    id: UUID
    type: str = Field(
        description="Stable event code, for example `company_registration_rejected`."
    )
    message: str
    details: dict[str, Any] | None = Field(
        default=None,
        description="Identifiers the client may use to link to the related item.",
    )
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
