from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.account_management.exceptions import InvalidCompletionRangeError
from app.account_management.schemas.account_list_response import AccountListResponse
from app.account_management.schemas.account_summary_response import (
    AccountSummaryResponse,
)
from app.candidates.domain.resume_completeness import missing_resume_fields
from app.candidates.services.resume_state import (
    resume_is_complete,
    resume_section_presence,
)
from app.db.models import AppUser, Candidate, Company, Resume
from app.db.models.enums import AccountStatus, CompanyStatus, UserType

MANAGED_USER_TYPES = (UserType.CANDIDATE, UserType.COMPANY)

_COMPLETION = func.coalesce(Resume.completion_percentage, 0)


def list_accounts(
    session: Session,
    *,
    user_type: UserType | None,
    account_status: AccountStatus | None,
    company_status: CompanyStatus | None,
    min_completion: int | None,
    max_completion: int | None,
    limit: int,
    offset: int,
    completeness: Literal["complete", "incomplete"] | None = None,
) -> AccountListResponse:
    if (
        min_completion is not None
        and max_completion is not None
        and min_completion > max_completion
    ):
        raise InvalidCompletionRangeError

    def filtered(statement: Select[Any]) -> Select[Any]:
        statement = (
            statement.select_from(AppUser)
            .outerjoin(Candidate, Candidate.id == AppUser.id)
            .outerjoin(Company, Company.id == AppUser.id)
            .outerjoin(Resume, Resume.candidate_id == Candidate.id)
            .where(AppUser.user_type.in_(MANAGED_USER_TYPES))
        )
        if user_type is not None:
            statement = statement.where(AppUser.user_type == user_type)
        if account_status is not None:
            statement = statement.where(AppUser.account_status == account_status)
        if company_status is not None:
            statement = statement.where(Company.status == company_status)
        if completeness is not None:
            statement = statement.where(
                AppUser.user_type == UserType.CANDIDATE,
                resume_is_complete()
                if completeness == "complete"
                else ~resume_is_complete(),
            )
        if min_completion is not None or max_completion is not None:
            statement = statement.where(
                AppUser.user_type == UserType.CANDIDATE,
                _COMPLETION.between(
                    min_completion or 0,
                    100 if max_completion is None else max_completion,
                ),
            )
        return statement

    total = session.scalar(filtered(select(func.count(AppUser.id)))) or 0
    rows = session.execute(
        filtered(
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
            )
        )
        .order_by(AppUser.created_at.desc(), AppUser.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return AccountListResponse(
        items=[
            AccountSummaryResponse(
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
            for row in rows
        ],
        total=total,
    )
