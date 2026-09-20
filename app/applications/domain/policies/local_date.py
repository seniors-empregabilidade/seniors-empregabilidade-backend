from datetime import date, datetime
from zoneinfo import ZoneInfo

# The product defines "today" and calendar-day boundaries in the company's
# operating timezone, not UTC. An instant just after midnight UTC can still
# be "yesterday" for a Brazil-based candidate or company, so every date
# comparison in this module (days in process, job closing dates) must convert
# through this timezone before calling `.date()`.
LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def to_local_date(moment: datetime) -> date:
    """Return the calendar date `moment` falls on in `LOCAL_TIMEZONE`."""
    return moment.astimezone(LOCAL_TIMEZONE).date()
