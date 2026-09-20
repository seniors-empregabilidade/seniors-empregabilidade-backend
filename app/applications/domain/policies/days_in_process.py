from datetime import datetime

from app.applications.domain.policies.local_date import to_local_date


def days_in_process(
    *, submitted_at: datetime, closed_at: datetime | None, now: datetime
) -> int:
    """Count full days between submission and the relevant reference point.

    An application still moving through the pipeline counts up to `now`. An
    application that already left the pipeline counts up to `closed_at`
    instead, so a candidate who withdrew last week does not keep accruing
    days just because they view the list today. Comparison uses calendar
    dates in `LOCAL_TIMEZONE` (America/Sao_Paulo), not elapsed hours and not
    the UTC calendar date: a submission recorded at 02:00 UTC already
    happened "yesterday" evening in that timezone, and using the raw UTC date
    would silently shift such boundary cases by a day.
    """
    reference = closed_at if closed_at is not None else now
    elapsed = (to_local_date(reference) - to_local_date(submitted_at)).days
    return max(elapsed, 0)
