from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas.current_user import CurrentUser
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.skills.domain import MAX_SKILL_NAME_LENGTH
from app.skills.schemas import SkillResponse
from app.skills.services import search_skills

DEFAULT_SUGGESTIONS = 20
MAX_SUGGESTIONS = 50

router = APIRouter(
    prefix="/skills",
    tags=["skills"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.get("", response_model=list[SkillResponse])
def list_skills(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    search: Annotated[str | None, Query(max_length=MAX_SKILL_NAME_LENGTH)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_SUGGESTIONS)] = DEFAULT_SUGGESTIONS,
) -> list[SkillResponse]:
    del current_user
    found = search_skills(session=session, search=search, limit=limit)
    return [
        SkillResponse(id=skill.id, name=skill.name, type=skill.type) for skill in found
    ]
