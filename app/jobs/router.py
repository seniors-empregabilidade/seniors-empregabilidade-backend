from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_approved_company, require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.jobs.schemas import CreateJobRequest, JobResponse, JobSearchResultResponse
from app.jobs.services import JobRecord, list_company_jobs, publish_job, search_jobs
from app.skills.schemas import SkillResponse

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_SEARCH_LENGTH = 150
MAX_OFFSET = 2**63 - 1  # PostgreSQL bigint

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


@router.get("", response_model=list[JobSearchResultResponse])
def list_open_jobs(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    search: Annotated[
        str | None,
        Query(max_length=MAX_SEARCH_LENGTH, description="Partial job title filter"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> list[JobSearchResultResponse]:
    response.headers["Cache-Control"] = "no-store"
    found = search_jobs(
        session, candidate_id=user.id, search=search, limit=limit, offset=offset
    )
    return [
        JobSearchResultResponse(
            id=job.id,
            title=job.title,
            company_name=job.company_name,
            location=job.location,
            work_mode=job.work_mode,
            salary_max=job.salary_max,
            published_at=job.published_at,
            days_since_published=job.days_since_published,
            matched_skill_count=job.matched_skill_count,
            required_skill_count=job.required_skill_count,
            missing_skills=[
                SkillResponse(id=skill.id, name=skill.name, type=skill.type)
                for skill in job.missing_skills
            ],
        )
        for job in found
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
