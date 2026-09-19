from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.applications.schemas.application_summary_response import (
    ApplicationSummaryResponse,
)
from app.applications.services.list_my_applications import list_my_applications
from app.applications.services.withdraw_application import withdraw_application
from app.auth.dependencies import require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session

router = APIRouter(
    prefix="/applications",
    tags=["applications"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403)},
)


@router.get("/me", response_model=list[ApplicationSummaryResponse])
def read_my_applications(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    company_name: Annotated[
        str | None,
        Query(min_length=1, max_length=200, description="Partial company name filter"),
    ] = None,
) -> list[ApplicationSummaryResponse]:
    response.headers["Cache-Control"] = "no-store"
    return list_my_applications(
        session, candidate_id=user.id, company_name=company_name
    )


@router.post(
    "/{application_id}/withdraw",
    response_model=ApplicationSummaryResponse,
    responses={code: PROBLEM_RESPONSE for code in (404, 409)},
)
def withdraw_my_application(
    application_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationSummaryResponse:
    response.headers["Cache-Control"] = "no-store"
    return withdraw_application(
        session, application_id=application_id, candidate_id=user.id
    )
