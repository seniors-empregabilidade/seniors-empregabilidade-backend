from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.account_management.schemas.account_detail_response import AccountDetailResponse
from app.account_management.schemas.account_list_response import AccountListResponse
from app.account_management.schemas.account_status_request import AccountStatusRequest
from app.account_management.schemas.account_status_response import (
    AccountStatusResponse,
)
from app.account_management.services.account_filters import AccountFilters
from app.account_management.services.change_account_status import (
    change_account_status,
)
from app.account_management.services.export_accounts import export_accounts
from app.account_management.services.get_account import get_account
from app.account_management.services.list_accounts import list_accounts
from app.auth.dependencies import require_administrator
from app.auth.schemas.current_user import CurrentUser
from app.core.csv_document import CSV_MEDIA_TYPE, csv_attachment
from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.models.enums import AccountStatus, CompanyStatus, UserType
from app.db.session import get_session

router = APIRouter(
    prefix="/admin/accounts",
    tags=["account-management"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


def account_filters(
    user_type: Annotated[
        Literal["candidate", "company"] | None,
        Query(description="Account type"),
    ] = None,
    account_status: Annotated[
        AccountStatus | None, Query(description="Account status")
    ] = None,
    company_status: Annotated[
        CompanyStatus | None,
        Query(description="Company approval situation; matches companies only"),
    ] = None,
    min_completion: Annotated[
        int | None,
        Query(ge=0, le=100, description="Minimum résumé completion; candidates only"),
    ] = None,
    max_completion: Annotated[
        int | None,
        Query(ge=0, le=100, description="Maximum résumé completion; candidates only"),
    ] = None,
    completeness: Annotated[Literal["complete", "incomplete"] | None, Query()] = None,
) -> AccountFilters:
    return AccountFilters(
        user_type=UserType(user_type) if user_type else None,
        account_status=account_status,
        company_status=company_status,
        min_completion=min_completion,
        max_completion=max_completion,
        completeness=completeness,
    )


@router.get("", response_model=AccountListResponse)
def read_accounts(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AccountFilters, Depends(account_filters)],
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> AccountListResponse:
    response.headers["Cache-Control"] = "no-store"
    return list_accounts(session, filters, limit=limit, offset=offset)


@router.get(
    "/export",
    response_class=Response,
    responses={
        200: {
            "content": {CSV_MEDIA_TYPE: {}},
            "description": "Every account matching the filters, as a CSV file.",
        }
    },
)
def export_account_list(
    user: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AccountFilters, Depends(account_filters)],
) -> Response:
    return csv_attachment(
        export_accounts(session, administrator_id=user.id, filters=filters)
    )


@router.get(
    "/{account_id}",
    response_model=AccountDetailResponse,
    responses={404: PROBLEM_RESPONSE},
)
def read_account(
    account_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> AccountDetailResponse:
    response.headers["Cache-Control"] = "no-store"
    return get_account(session, account_id)


@router.patch(
    "/{account_id}/status",
    response_model=AccountStatusResponse,
    responses={code: PROBLEM_RESPONSE for code in (404, 409)},
)
def edit_account_status(
    account_id: UUID,
    request: AccountStatusRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> AccountStatusResponse:
    response.headers["Cache-Control"] = "no-store"
    return change_account_status(
        session,
        administrator_id=user.id,
        account_id=account_id,
        request=request,
    )
