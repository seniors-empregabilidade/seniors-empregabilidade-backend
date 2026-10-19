from datetime import timedelta

import pytest

from app.notifications.domain.email_retry_policy import gives_up, retry_delay


@pytest.mark.parametrize(
    ("failed_attempts", "minutes"),
    [(1, 1), (2, 2), (3, 4), (4, 8), (7, 60), (30, 60)],
)
def test_retry_delay_doubles_up_to_one_hour(failed_attempts: int, minutes: int) -> None:
    assert retry_delay(failed_attempts) == timedelta(minutes=minutes)


def test_retry_delay_needs_a_failed_attempt() -> None:
    with pytest.raises(ValueError):
        retry_delay(0)


@pytest.mark.parametrize(
    ("failed_attempts", "expected"), [(4, False), (5, True), (6, True)]
)
def test_gives_up_at_the_maximum(failed_attempts: int, expected: bool) -> None:
    assert gives_up(failed_attempts, max_attempts=5) is expected
