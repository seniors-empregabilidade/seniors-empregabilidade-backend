from pydantic import BaseModel, Field

from app.notifications.schemas.notification_response import NotificationResponse


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int = Field(
        description="Every unread notification of the user, ignoring pagination."
    )
    next_cursor: str | None = Field(
        description=(
            "Opaque token for the next page, sent back as `cursor`; "
            "`null` on the last page."
        )
    )
