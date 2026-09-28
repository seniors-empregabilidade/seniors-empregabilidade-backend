from datetime import datetime

from app.core.local_date import to_local_date


def days_since_published(*, published_at: datetime, now: datetime) -> int:
    """Count calendar days in `LOCAL_TIMEZONE`, like `days_in_process`."""
    return max((to_local_date(now) - to_local_date(published_at)).days, 0)
