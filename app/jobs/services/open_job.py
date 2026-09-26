from datetime import datetime

from sqlalchemy import ColumnElement, and_

from app.core.local_date import to_local_date
from app.db.models import Job
from app.db.models.enums import JobStatus


def is_open_at(now: datetime) -> ColumnElement[bool]:
    """Published and not past its closing date in `LOCAL_TIMEZONE`."""
    return and_(
        Job.status == JobStatus.PUBLISHED, Job.closing_date >= to_local_date(now)
    )
