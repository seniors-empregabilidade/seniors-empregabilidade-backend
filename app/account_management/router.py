from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.account_management.schemas.account_list_response import AccountListResponse
from app.account_management.schemas.account_status_request import AccountStatusRequest
from app.account_management.schemas.account_status_response import (
    AccountStatusResponse,
)
from app.account_management.services.change_account_status import (
    change_account_status,
)
from app.account_management.services.list_accounts import list_accounts
from app.auth.dependencies import require_administrator
from app.auth.schemas.current_user import CurrentUser
from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.models.enums import AccountStatus, CompanyStatus, UserType
from app.db.session import get_session

router = APIRouter(
    prefix="/admin/accounts",
    tags=["account-management"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.get(
    "",
    response_model=AccountListResponse,
    responses={code: PROBLEM_RESPONSE for code in (422,)},
)
def read_accounts(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
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
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> AccountListResponse:
    response.headers["Cache-Control"] = "no-store"
    return list_accounts(
        session,
        user_type=UserType(user_type) if user_type else None,
        account_status=account_status,
        company_status=company_status,
        min_completion=min_completion,
        max_completion=max_completion,
        limit=limit,
        offset=offset,
    )


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
