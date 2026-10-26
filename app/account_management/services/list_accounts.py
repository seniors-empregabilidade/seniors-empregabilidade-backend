from typing import Any

from sqlalchemy import Row, Select, func, select
from sqlalchemy.orm import Session

from app.account_management.exceptions import InvalidCompletionRangeError
from app.account_management.schemas.account_list_response import AccountListResponse
from app.account_management.schemas.account_summary_response import (
    AccountSummaryResponse,
)
from app.account_management.services.account_filters import AccountFilters
from app.candidates.domain.resume_completeness import missing_resume_fields
from app.candidates.services.resume_state import (
    resume_is_complete,
    resume_section_presence,
)
from app.db.models import AppUser, Candidate, Company, Resume
from app.db.models.enums import UserType

MANAGED_USER_TYPES = (UserType.CANDIDATE, UserType.COMPANY)

_COMPLETION = func.coalesce(Resume.completion_percentage, 0)


def list_accounts(
    session: Session,
    filters: AccountFilters,
    *,
    limit: int,
    offset: int,
) -> AccountListResponse:
    items = account_summaries(session, filters, limit=limit, offset=offset)
    total = session.scalar(_filtered(select(func.count(AppUser.id)), filters)) or 0
    return AccountListResponse(items=items, total=total)


def account_summaries(
    session: Session,
    filters: AccountFilters,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[AccountSummaryResponse]:
    """Accounts matching `filters`, newest first; every match when `limit` is None."""
    if (
        filters.min_completion is not None
        and filters.max_completion is not None
        and filters.min_completion > filters.max_completion
    ):
        raise InvalidCompletionRangeError

    rows = session.execute(
        _filtered(
            select(
                AppUser.id,
                AppUser.user_type,
                AppUser.email,
                AppUser.account_status,
                AppUser.created_at,
                Candidate.full_name,
                Company.trade_name,
                Company.legal_name,
                Company.status,
                Resume.completion_percentage,
                Candidate.city,
                Candidate.state,
                Resume.summary,
                *[
                    expression.label(name)
                    for expression, name in zip(
                        resume_section_presence(),
                        ("has_experience", "has_education", "has_skill"),
                        strict=True,
                    )
                ],
            ),
            filters,
        )
        .order_by(AppUser.created_at.desc(), AppUser.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [_summary(row) for row in rows]


def _filtered(statement: Select[Any], filters: AccountFilters) -> Select[Any]:
    statement = (
        statement.select_from(AppUser)
        .outerjoin(Candidate, Candidate.id == AppUser.id)
        .outerjoin(Company, Company.id == AppUser.id)
        .outerjoin(Resume, Resume.candidate_id == Candidate.id)
        .where(AppUser.user_type.in_(MANAGED_USER_TYPES))
    )
    if filters.user_type is not None:
        statement = statement.where(AppUser.user_type == filters.user_type)
    if filters.account_status is not None:
        statement = statement.where(AppUser.account_status == filters.account_status)
    if filters.company_status is not None:
        statement = statement.where(Company.status == filters.company_status)
    if filters.completeness is not None:
        statement = statement.where(
            AppUser.user_type == UserType.CANDIDATE,
            resume_is_complete()
            if filters.completeness == "complete"
            else ~resume_is_complete(),
        )
    if filters.min_completion is not None or filters.max_completion is not None:
        statement = statement.where(
            AppUser.user_type == UserType.CANDIDATE,
            _COMPLETION.between(
                filters.min_completion or 0,
                100 if filters.max_completion is None else filters.max_completion,
            ),
        )
    return statement


def _summary(row: Row[Any]) -> AccountSummaryResponse:
    return AccountSummaryResponse(
        id=row.id,
        user_type=row.user_type,
        email=row.email,
        display_name=row.full_name or row.trade_name or row.legal_name,
        account_status=row.account_status,
        company_status=row.status,
        completion_percentage=(
            (row.completion_percentage or 0)
            if row.user_type == UserType.CANDIDATE
            else None
        ),
        created_at=row.created_at,
        missing_fields=list(
            missing_resume_fields(
                city=row.city,
                state=row.state,
                summary=row.summary,
                has_experience=row.has_experience,
                has_education=row.has_education,
                has_skill=row.has_skill,
            )
        )
        if row.user_type == UserType.CANDIDATE
        else None,
    )
