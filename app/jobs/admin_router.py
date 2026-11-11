from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_administrator
from app.auth.schemas.current_user import CurrentUser
from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.jobs.router import MAX_SEARCH_LENGTH
from app.jobs.schemas import AdminJobListResponse
from app.jobs.services import list_jobs_for_administration

router = APIRouter(
    prefix="/admin/jobs",
    tags=["jobs"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.get("", response_model=AdminJobListResponse)
def read_jobs_for_administration(
    response: Response,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    search: Annotated[
        str | None,
        Query(max_length=MAX_SEARCH_LENGTH, description="Partial job title filter"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> AdminJobListResponse:
    response.headers["Cache-Control"] = "no-store"
    return list_jobs_for_administration(
        session, search=search, limit=limit, offset=offset
    )
