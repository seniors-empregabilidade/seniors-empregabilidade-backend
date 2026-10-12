from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
