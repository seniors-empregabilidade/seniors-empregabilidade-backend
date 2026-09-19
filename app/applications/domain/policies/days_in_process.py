from datetime import datetime


def days_in_process(
    *, submitted_at: datetime, closed_at: datetime | None, now: datetime
) -> int:
    """Count full days between submission and the relevant reference point.

    An application still moving through the pipeline counts up to `now`. An
    application that already left the pipeline counts up to `closed_at`
    instead, so a candidate who withdrew last week does not keep accruing
    days just because they view the list today. Comparison uses calendar
    dates (not elapsed hours) so the result matches how a person reads "days
    in process": the count is not affected by the time of day the candidate
    applied or the process closed.
    """
    reference = closed_at if closed_at is not None else now
    elapsed = (reference.date() - submitted_at.date()).days
    return max(elapsed, 0)
