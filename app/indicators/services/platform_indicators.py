"""Platform indicators aggregation.

The calculation rules are documented in docs/INDICATORS.md and must be kept in
sync with this module.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import QueryableAttribute, Session, aliased

from app.candidates.services.resume_state import resume_is_complete
from app.core.errors import ProblemException
from app.core.local_date import LOCAL_TIMEZONE, to_local_date
from app.db.models.app_user import AppUser
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.company import Company
from app.db.models.enums import (
    AccountStatus,
    CompanyStatus,
    EmploymentStatus,
    JobStatus,
)
from app.db.models.job import Job
from app.db.models.job_skill import JobSkill
from app.db.models.resume import Resume
from app.db.models.resume_skill import ResumeSkill
from app.indicators.schemas.indicator_filters import IndicatorFilters
from app.indicators.schemas.platform_indicators import (
    AppliedFilters,
    IndicatorSegments,
    IndicatorTotals,
    PlatformIndicators,
)
from app.jobs.domain.value_objects.compatibility_score import (
    HIGHLIGHT_THRESHOLD_PERCENT,
)


@dataclass(frozen=True)
class _Period:
    """Inclusive calendar-day bounds in the product's operating timezone."""

    start: datetime | None
    end: datetime | None


def get_platform_indicators(
    session: Session, filters: IndicatorFilters, *, now: datetime | None = None
) -> PlatformIndicators:
    _ensure_valid_period(filters)
    period = _period_of(filters)
    return PlatformIndicators(
        filters=_applied(filters),
        totals=IndicatorTotals(
            candidates=_count(session, _candidates(filters, period)),
            companies=_count(session, _companies(filters, period)),
            jobs=_count(session, _jobs(filters, period)),
            applications=_count(session, _applications(filters, period)),
            matches=_count(
                session, _matches(filters, period, now or datetime.now(UTC))
            ),
        ),
        segments=IndicatorSegments(
            candidates_without_placement=_count(
                session, _candidates_without_placement(filters, period)
            ),
            candidates_with_unknown_employment=_count(
                session,
                _candidates(filters, period)
                .outerjoin(Resume, Resume.candidate_id == Candidate.id)
                .where(Resume.employment_status.is_(None)),
            ),
            incomplete_resumes=_count(session, _incomplete_resumes(filters, period)),
        ),
    )


def _ensure_valid_period(filters: IndicatorFilters) -> None:
    if filters.start_date is None or filters.end_date is None:
        return
    if filters.start_date <= filters.end_date:
        return
    raise ProblemException(
        status_code=422,
        title="Unprocessable Entity",
        code="invalid_period",
        detail="start_date must not be after end_date.",
    )


def _period_of(filters: IndicatorFilters) -> _Period:
    return _Period(start=_start_of(filters.start_date), end=_end_of(filters.end_date))


def _start_of(day: date | None) -> datetime | None:
    if day is None:
        return None
    return datetime.combine(day, time.min, tzinfo=LOCAL_TIMEZONE)


def _end_of(day: date | None) -> datetime | None:
    if day is None:
        return None
    return datetime.combine(day, time.max, tzinfo=LOCAL_TIMEZONE)


def _applied(filters: IndicatorFilters) -> AppliedFilters:
    return AppliedFilters(
        start_date=filters.start_date,
        end_date=filters.end_date,
        account_status=filters.account_status,
        candidate_availability=filters.candidate_availability,
        company_status=filters.company_status,
        job_status=filters.job_status,
        application_status=filters.application_status,
    )


def _count(session: Session, statement: Select[tuple[int]]) -> int:
    return session.scalar(statement) or 0


def _within(
    column: QueryableAttribute[datetime], period: _Period
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if period.start is not None:
        conditions.append(column >= period.start)
    if period.end is not None:
        conditions.append(column <= period.end)
    return conditions


def _candidates(filters: IndicatorFilters, period: _Period) -> Select[tuple[int]]:
    conditions = _within(AppUser.created_at, period)
    if filters.account_status is not None:
        conditions.append(AppUser.account_status == filters.account_status)
    if filters.candidate_availability is not None:
        conditions.append(Candidate.availability == filters.candidate_availability)
    return (
        select(func.count())
        .select_from(Candidate)
        .join(AppUser, AppUser.id == Candidate.id)
        .where(*conditions)
    )


def _companies(filters: IndicatorFilters, period: _Period) -> Select[tuple[int]]:
    conditions = _within(AppUser.created_at, period)
    if filters.account_status is not None:
        conditions.append(AppUser.account_status == filters.account_status)
    if filters.company_status is not None:
        conditions.append(Company.status == filters.company_status)
    return (
        select(func.count())
        .select_from(Company)
        .join(AppUser, AppUser.id == Company.id)
        .where(*conditions)
    )


def _jobs(filters: IndicatorFilters, period: _Period) -> Select[tuple[int]]:
    conditions = _within(Job.created_at, period)
    if filters.job_status is not None:
        conditions.append(Job.status == filters.job_status)
    return select(func.count()).select_from(Job).where(*conditions)


def _applications(filters: IndicatorFilters, period: _Period) -> Select[tuple[int]]:
    conditions = _within(Application.created_at, period)
    if filters.application_status is not None:
        conditions.append(Application.status == filters.application_status)
    return select(func.count()).select_from(Application).where(*conditions)


def _matches(
    filters: IndicatorFilters, period: _Period, now: datetime
) -> Select[tuple[int]]:
    candidate_account = aliased(AppUser)
    company_account = aliased(AppUser)
    requirements = (
        select(func.count(JobSkill.skill_id))
        .where(JobSkill.job_id == Job.id)
        .correlate(Job)
        .scalar_subquery()
    )
    conditions: list[ColumnElement[bool]] = [
        Job.status == JobStatus.PUBLISHED,
        Job.closing_date >= to_local_date(now),
        Company.status == CompanyStatus.APPROVED,
        company_account.account_status == AccountStatus.ACTIVE,
        candidate_account.account_status == AccountStatus.ACTIVE,
        *_within(Job.created_at, period),
        *_within(candidate_account.created_at, period),
    ]
    if filters.account_status is not None:
        conditions.append(candidate_account.account_status == filters.account_status)
    if filters.candidate_availability is not None:
        conditions.append(Candidate.availability == filters.candidate_availability)
    if filters.company_status is not None:
        conditions.append(Company.status == filters.company_status)
    if filters.job_status is not None:
        conditions.append(Job.status == filters.job_status)
    pairs = (
        select(Job.id, Candidate.id)
        .select_from(Job)
        .join(Company, Company.id == Job.company_id)
        .join(company_account, company_account.id == Company.id)
        .join(JobSkill, JobSkill.job_id == Job.id)
        .join(ResumeSkill, ResumeSkill.skill_id == JobSkill.skill_id)
        .join(Resume, Resume.id == ResumeSkill.resume_id)
        .join(Candidate, Candidate.id == Resume.candidate_id)
        .join(candidate_account, candidate_account.id == Candidate.id)
        .where(*conditions)
        .group_by(Job.id, Candidate.id)
        .having(
            func.count(ResumeSkill.skill_id) * 100
            >= HIGHLIGHT_THRESHOLD_PERCENT * requirements
        )
    )
    return select(func.count()).select_from(pairs.subquery())


def _candidates_without_placement(
    filters: IndicatorFilters, period: _Period
) -> Select[tuple[int]]:
    return (
        _candidates(filters, period)
        .join(Resume, Resume.candidate_id == Candidate.id)
        .where(Resume.employment_status == EmploymentStatus.UNEMPLOYED)
    )


def _incomplete_resumes(
    filters: IndicatorFilters, period: _Period
) -> Select[tuple[int]]:
    return (
        _candidates(filters, period)
        .outerjoin(Resume, Resume.candidate_id == Candidate.id)
        .where(~resume_is_complete())
    )
