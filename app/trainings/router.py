from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas.current_user import CurrentUser
from app.core.pagination import MAX_OFFSET
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.skills.domain import MAX_SKILL_NAME_LENGTH
from app.trainings.schemas import PublishedTrainingListResponse
from app.trainings.services import search_trainings_by_skill

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50

router = APIRouter(
    prefix="/trainings",
    tags=["trainings"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.get("", response_model=PublishedTrainingListResponse)
def search_trainings(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    skill: Annotated[str | None, Query(max_length=MAX_SKILL_NAME_LENGTH)] = None,
    skill_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> PublishedTrainingListResponse:
    del current_user
    return search_trainings_by_skill(
        session, skill=skill, skill_id=skill_id, limit=limit, offset=offset
    )
