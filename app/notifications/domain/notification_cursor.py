import binascii
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

_SEPARATOR = "|"


class InvalidNotificationCursor(ValueError):
    """The client sent a cursor this API did not produce."""


@dataclass(frozen=True, slots=True)
class NotificationCursor:
    """Position after the last notification of a page, newest first.

    The listing orders by `(created_at, id)` descending, so the next page holds
    every notification strictly before this pair. Unlike an offset, the
    position does not move when earlier items are marked as read or a new
    notification arrives between requests.

    Clients treat the encoded token as opaque; its format may change.
    """

    created_at: datetime
    id: UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}{_SEPARATOR}{self.id}"
        return urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, token: str) -> Self:
        try:
            padded = token + "=" * (-len(token) % 4)
            raw = urlsafe_b64decode(padded.encode("ascii")).decode()
            created_at_text, id_text = raw.split(_SEPARATOR)
            created_at = datetime.fromisoformat(created_at_text)
            notification_id = UUID(id_text)
        except (binascii.Error, UnicodeError, ValueError) as exc:
            raise InvalidNotificationCursor from exc
        if created_at.tzinfo is None:
            raise InvalidNotificationCursor
        return cls(created_at=created_at, id=notification_id)
