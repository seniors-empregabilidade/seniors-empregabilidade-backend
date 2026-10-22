from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models import AppUser, Company, Job
from app.db.models.enums import (
    AccountStatus,
    CompanyStatus,
    JobStatus,
    UserType,
    WorkMode,
)
from app.jobs.services import search_jobs

pytestmark = pytest.mark.integration

# 01:00 UTC on Sep 10 is still 22:00 on Sep 9 in America/Sao_Paulo.
NOW = datetime(2026, 9, 10, 1, 0, tzinfo=UTC)


def test_closing_and_publication_dates_follow_the_sao_paulo_calendar(
    database_session: Session,
) -> None:
    marker = f"jobsearch{uuid4().hex[:10]}"
    user = AppUser(
        email=f"{marker}@company.example.invalid",
        identity_subject=None,
        user_type=UserType.COMPANY,
    )
    database_session.add(user)
    database_session.flush()
    database_session.add(
        Company(
            id=user.id,
            cnpj=f"{uuid4().int % 10**14:014d}",
            legal_name="Synthetic Calendar Company",
            corporate_email=user.email,
            status=CompanyStatus.APPROVED,
        )
    )

    def job(title: str, closing_date: date) -> Job:
        return Job(
            company_id=user.id,
            title=f"{marker} {title}",
            description="Synthetic job for calendar tests.",
            work_mode=WorkMode.REMOTE,
            status=JobStatus.PUBLISHED,
            closing_date=closing_date,
            published_at=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        )

    closing_today = job("Closing Today", date(2026, 9, 9))
    closed_yesterday = job("Closed Yesterday", date(2026, 9, 8))
    database_session.add_all((closing_today, closed_yesterday))
    database_session.flush()

    found = search_jobs(
        database_session,
        candidate_id=uuid4(),
        search=marker,
        limit=10,
        offset=0,
        now=NOW,
    )

    assert [job.id for job in found] == [closing_today.id]
    assert found[0].days_since_published == 0


def test_an_open_job_of_a_blocked_company_is_omitted(
    database_session: Session,
) -> None:
    marker = f"jobsearch{uuid4().hex[:10]}"

    def company(name: str, status: AccountStatus) -> AppUser:
        user = AppUser(
            email=f"{marker}-{status.value}@company.example.invalid",
            identity_subject=None,
            user_type=UserType.COMPANY,
            account_status=status,
        )
        database_session.add(user)
        database_session.flush()
        database_session.add(
            Company(
                id=user.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name=name,
                corporate_email=user.email,
                status=CompanyStatus.APPROVED,
            )
        )
        return user

    active = company("Synthetic Active Company", AccountStatus.ACTIVE)
    blocked = company("Synthetic Blocked Company", AccountStatus.BLOCKED)

    def job(owner: AppUser, title: str) -> Job:
        return Job(
            company_id=owner.id,
            title=f"{marker} {title}",
            description="Synthetic job for account-status tests.",
            work_mode=WorkMode.REMOTE,
            status=JobStatus.PUBLISHED,
            closing_date=date(2099, 12, 31),
            published_at=NOW,
        )

    visible = job(active, "Visible Role")
    hidden = job(blocked, "Hidden Role")
    database_session.add_all((visible, hidden))
    database_session.flush()

    found = search_jobs(
        database_session,
        candidate_id=uuid4(),
        search=marker,
        limit=10,
        offset=0,
        now=NOW,
    )

    assert [item.id for item in found] == [visible.id]
