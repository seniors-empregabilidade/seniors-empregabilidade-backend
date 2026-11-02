from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_administrator
from app.auth.schemas.current_user import CurrentUser
from app.core.pagination import MAX_OFFSET
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.models.enums import SkillType
from app.db.session import get_session
from app.skills.domain import MAX_SKILL_NAME_LENGTH
from app.skills.schemas import (
    CatalogSkillListResponse,
    CatalogSkillResponse,
    CatalogSkillUpdateRequest,
    SkillRequest,
    SkillStatus,
)
from app.skills.services import (
    create_catalog_skill,
    list_catalog_skills,
    update_catalog_skill,
)

DEFAULT_CATALOG_PAGE_SIZE = 20
MAX_CATALOG_PAGE_SIZE = 50

router = APIRouter(
    prefix="/admin/skills",
    tags=["skill-catalog"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.get("", response_model=CatalogSkillListResponse)
def read_catalog_skills(
    response: Response,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=MAX_SKILL_NAME_LENGTH)] = None,
    skill_type: Annotated[SkillType | None, Query(alias="type")] = None,
    status: Annotated[SkillStatus | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_CATALOG_PAGE_SIZE)
    ] = DEFAULT_CATALOG_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> CatalogSkillListResponse:
    response.headers["Cache-Control"] = "no-store"
    return list_catalog_skills(
        session,
        search=search,
        skill_type=skill_type,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=CatalogSkillResponse,
    status_code=201,
    responses={409: PROBLEM_RESPONSE},
)
def create_skill(
    request: SkillRequest,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> CatalogSkillResponse:
    return create_catalog_skill(session, request)


@router.patch(
    "/{skill_id}",
    response_model=CatalogSkillResponse,
    responses={code: PROBLEM_RESPONSE for code in (404, 409)},
)
def update_skill(
    skill_id: UUID,
    request: CatalogSkillUpdateRequest,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
) -> CatalogSkillResponse:
    return update_catalog_skill(session, skill_id, request)
