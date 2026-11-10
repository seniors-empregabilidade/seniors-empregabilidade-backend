from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_administrator
from app.auth.schemas.current_user import CurrentUser
from app.core.pagination import MAX_OFFSET
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.trainings.schemas import (
    MAX_TITLE_LENGTH,
    TrainingListResponse,
    TrainingRequest,
    TrainingResponse,
    TrainingUpdateRequest,
)
from app.trainings.services import (
    create_training,
    delete_training,
    get_training,
    list_trainings,
    update_training,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50

router = APIRouter(
    prefix="/admin/trainings",
    tags=["training-catalog"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.get("", response_model=TrainingListResponse)
def read_trainings(
    response: Response,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=MAX_TITLE_LENGTH)] = None,
    skill_id: Annotated[UUID | None, Query()] = None,
    published: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> TrainingListResponse:
    response.headers["Cache-Control"] = "no-store"
    return list_trainings(
        session,
        search=search,
        skill_id=skill_id,
        published=published,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=TrainingResponse,
    status_code=201,
)
def create_training_entry(
    request: TrainingRequest,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> TrainingResponse:
    return create_training(session, request)


@router.get(
    "/{training_id}",
    response_model=TrainingResponse,
    responses={404: PROBLEM_RESPONSE},
)
def read_training(
    training_id: UUID,
    response: Response,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> TrainingResponse:
    response.headers["Cache-Control"] = "no-store"
    return get_training(session, training_id)


@router.patch(
    "/{training_id}",
    response_model=TrainingResponse,
    responses={404: PROBLEM_RESPONSE},
)
def update_training_entry(
    training_id: UUID,
    request: TrainingUpdateRequest,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> TrainingResponse:
    return update_training(session, training_id, request)


@router.delete(
    "/{training_id}",
    status_code=204,
    responses={404: PROBLEM_RESPONSE},
)
def delete_training_entry(
    training_id: UUID,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_training(session, training_id)
    return Response(status_code=204)
