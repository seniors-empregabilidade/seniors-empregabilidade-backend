from datetime import datetime

from sqlalchemy import ColumnElement, and_

from app.core.local_date import to_local_date
from app.db.models import AppUser, Job
from app.db.models.enums import AccountStatus, JobStatus


def is_open_at(now: datetime) -> ColumnElement[bool]:
    """Published and not past its closing date in `LOCAL_TIMEZONE`."""
    return and_(
        Job.status == JobStatus.PUBLISHED, Job.closing_date >= to_local_date(now)
    )


def publishing_company_is_not_blocked() -> ColumnElement[bool]:
    """The company account that owns the job is not `blocked`.

    The statement must join `AppUser` on `AppUser.id == Company.id`. A company
    and its `app_user` share that primary key. `suspended` is left visible:
    account management only assigns `active` and `blocked`.
    """
    return AppUser.account_status != AccountStatus.BLOCKED
