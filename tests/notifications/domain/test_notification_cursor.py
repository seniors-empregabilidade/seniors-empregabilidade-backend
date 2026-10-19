from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.notifications.domain.notification_cursor import (
    InvalidNotificationCursor,
    NotificationCursor,
)

POSITION = NotificationCursor(
    created_at=datetime(2026, 10, 14, 21, 30, 15, 123456, tzinfo=UTC),
    id=UUID("6f1c2b8e-3d4a-4f5b-9c6d-7e8f9a0b1c2d"),
)


def encode_raw(raw: str) -> str:
    return urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def test_cursor_round_trips_with_microseconds() -> None:
    assert NotificationCursor.decode(POSITION.encode()) == POSITION


def test_encoded_cursor_is_url_safe_without_padding() -> None:
    token = POSITION.encode()

    assert "=" not in token
    assert set(token) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )


@pytest.mark.parametrize(
    "token",
    [
        "not base64 at all!",
        "é",
        encode_raw("2026-10-14T21:30:15+00:00"),
        encode_raw("2026-10-14T21:30:15+00:00|extra|6f1c2b8e"),
        encode_raw("yesterday|6f1c2b8e-3d4a-4f5b-9c6d-7e8f9a0b1c2d"),
        encode_raw("2026-10-14T21:30:15+00:00|not-a-uuid"),
        encode_raw("2026-10-14T21:30:15|6f1c2b8e-3d4a-4f5b-9c6d-7e8f9a0b1c2d"),
    ],
    ids=[
        "not-base64",
        "non-ascii",
        "missing-id",
        "too-many-parts",
        "bad-timestamp",
        "bad-id",
        "naive-timestamp",
    ],
)
def test_foreign_cursor_is_rejected(token: str) -> None:
    with pytest.raises(InvalidNotificationCursor):
        NotificationCursor.decode(token)


def test_token_with_characters_outside_the_alphabet_is_rejected() -> None:
    # A lenient decoder would drop the extra characters and accept the token.
    with pytest.raises(InvalidNotificationCursor):
        NotificationCursor.decode(POSITION.encode() + "!!!!")


def test_cursor_cannot_be_built_with_a_naive_timestamp() -> None:
    with pytest.raises(InvalidNotificationCursor):
        NotificationCursor(
            created_at=datetime(2026, 10, 14, 21, 30, 15), id=POSITION.id
        )
