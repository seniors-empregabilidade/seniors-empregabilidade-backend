from datetime import UTC, datetime

from app.jobs.domain.policies.days_since_published import days_since_published


def test_counts_calendar_days_up_to_now() -> None:
    published_at = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)
    now = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)

    assert days_since_published(published_at=published_at, now=now) == 3


def test_uses_the_sao_paulo_calendar_date_not_utc() -> None:
    # Both instants fall on Sep 9 in America/Sao_Paulo (UTC-3), although the
    # second one is already Sep 10 in UTC.
    published_at = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    now = datetime(2026, 9, 10, 1, 0, tzinfo=UTC)

    assert days_since_published(published_at=published_at, now=now) == 0


def test_never_goes_negative() -> None:
    published_at = datetime(2026, 9, 10, tzinfo=UTC)
    now = datetime(2026, 9, 5, tzinfo=UTC)

    assert days_since_published(published_at=published_at, now=now) == 0
