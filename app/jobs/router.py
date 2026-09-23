from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_approved_company
from app.auth.schemas.current_user import CurrentUser
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.jobs.schemas import CreateJobRequest, JobResponse
from app.jobs.services import JobRecord, list_company_jobs, publish_job
from app.skills.schemas import SkillResponse

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403)},
)


@router.post(
    "",
    response_model=JobResponse,
    status_code=201,
    responses={422: PROBLEM_RESPONSE},
)
def create_job(
    request: CreateJobRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> JobResponse:
    response.headers["Cache-Control"] = "no-store"
    return _job_response(publish_job(request, session=session, company_id=user.id))


@router.get("/me", response_model=list[JobResponse])
def read_my_jobs(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> list[JobResponse]:
    response.headers["Cache-Control"] = "no-store"
    return [
        _job_response(record)
        for record in list_company_jobs(session=session, company_id=user.id)
    ]


def _job_response(record: JobRecord) -> JobResponse:
    return JobResponse(
        id=record.id,
        company_id=record.company_id,
        title=record.title,
        description=record.description,
        skills=[
            SkillResponse(id=skill.id, name=skill.name, type=skill.type)
            for skill in record.skills
        ],
        work_mode=record.work_mode,
        closing_date=record.closing_date,
        status=record.status,
        published_at=record.published_at,
        created_at=record.created_at,
    )
