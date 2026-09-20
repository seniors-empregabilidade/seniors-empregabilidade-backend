from datetime import UTC, datetime

from app.applications.domain.policies.days_in_process import days_in_process


def test_active_application_counts_up_to_now() -> None:
    submitted_at = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    now = datetime(2026, 9, 11, 23, 0, tzinfo=UTC)

    assert days_in_process(submitted_at=submitted_at, closed_at=None, now=now) == 10


def test_closed_application_counts_up_to_closing_date_not_now() -> None:
    submitted_at = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    closed_at = datetime(2026, 9, 6, 8, 0, tzinfo=UTC)
    now = datetime(2026, 9, 20, 23, 0, tzinfo=UTC)

    assert days_in_process(submitted_at=submitted_at, closed_at=closed_at, now=now) == 5


def test_same_day_submission_and_reference_counts_zero_days() -> None:
    submitted_at = datetime(2026, 9, 1, 22, 0, tzinfo=UTC)
    now = datetime(2026, 9, 1, 23, 0, tzinfo=UTC)

    assert days_in_process(submitted_at=submitted_at, closed_at=None, now=now) == 0


def test_result_never_goes_negative_even_with_an_inconsistent_reference() -> None:
    submitted_at = datetime(2026, 9, 10, tzinfo=UTC)
    closed_at = datetime(2026, 9, 5, tzinfo=UTC)
    now = datetime(2026, 9, 20, tzinfo=UTC)

    assert days_in_process(submitted_at=submitted_at, closed_at=closed_at, now=now) == 0


def test_active_application_uses_the_sao_paulo_calendar_date_not_utc() -> None:
    # 02:00 UTC is still 23:00 the previous day in America/Sao_Paulo
    # (UTC-3), so the UTC calendar date alone would understate the count.
    submitted_at = datetime(2026, 9, 10, 2, 0, tzinfo=UTC)  # Sep 9, 23:00 -03:00
    now = datetime(2026, 9, 10, 4, 0, tzinfo=UTC)  # Sep 10, 01:00 -03:00

    # Naively comparing UTC dates would give 0 (both fall on Sep 10 UTC);
    # comparing Sao Paulo dates correctly gives 1 (Sep 9 to Sep 10).
    assert days_in_process(submitted_at=submitted_at, closed_at=None, now=now) == 1


def test_closed_application_uses_the_sao_paulo_calendar_date_not_utc() -> None:
    submitted_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)  # Sep 1, 09:00 -03:00
    closed_at = datetime(2026, 9, 10, 2, 0, tzinfo=UTC)  # Sep 9, 23:00 -03:00
    now = datetime(2026, 9, 20, tzinfo=UTC)

    # Naively comparing UTC dates would give 9 (Sep 1 to Sep 10 UTC);
    # comparing Sao Paulo dates correctly gives 8 (Sep 1 to Sep 9).
    assert days_in_process(submitted_at=submitted_at, closed_at=closed_at, now=now) == 8
