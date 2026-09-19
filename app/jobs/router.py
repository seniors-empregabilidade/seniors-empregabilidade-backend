from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_approved_company
from app.auth.schemas.current_user import CurrentUser
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.jobs.schemas import CreateJobRequest, JobResponse
from app.jobs.services import publish_job
from app.skills.schemas import SkillResponse

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.post("", response_model=JobResponse, status_code=201)
def create_job(
    request: CreateJobRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> JobResponse:
    response.headers["Cache-Control"] = "no-store"
    published = publish_job(request, session=session, company_id=user.id)
    return JobResponse(
        id=published.id,
        company_id=published.company_id,
        title=published.title,
        description=published.description,
        skills=[
            SkillResponse(id=skill.id, name=skill.name, type=skill.type)
            for skill in published.skills
        ],
        work_mode=published.work_mode,
        closing_date=published.closing_date,
        status=published.status,
        published_at=published.published_at,
        created_at=published.created_at,
    )
