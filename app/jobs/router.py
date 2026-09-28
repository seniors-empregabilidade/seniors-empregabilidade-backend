from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_approved_company, require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.jobs.schemas import (
    CreateJobRequest,
    JobResponse,
    JobSummaryResponse,
    UpdateJobRequest,
    UpdateJobStatusRequest,
)
from app.jobs.services import (
    JobSnapshot,
    JobSummary,
    change_job_status,
    list_my_jobs,
    publish_job,
    update_job,
)
from app.jobs.schemas import CreateJobRequest, JobResponse, JobSearchResultResponse
from app.jobs.services import publish_job, search_jobs
from app.skills.schemas import SkillResponse
from app.skills.services import CatalogSkill

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_SEARCH_LENGTH = 150
MAX_OFFSET = 2**63 - 1  # PostgreSQL bigint

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


def _skill_responses(skills: Sequence[CatalogSkill]) -> list[SkillResponse]:
    return [
        SkillResponse(id=skill.id, name=skill.name, type=skill.type) for skill in skills
    ]


def _to_job_response(job: JobSnapshot) -> JobResponse:
    return JobResponse(
        id=job.id,
        company_id=job.company_id,
        title=job.title,
        description=job.description,
        skills=_skill_responses(job.skills),
        work_mode=job.work_mode,
        closing_date=job.closing_date,
        status=job.status,
        published_at=job.published_at,
        created_at=job.created_at,
    )


def _to_summary_response(job: JobSummary) -> JobSummaryResponse:
    return JobSummaryResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        skills=_skill_responses(job.skills),
        work_mode=job.work_mode,
        closing_date=job.closing_date,
        status=job.status,
        published_at=job.published_at,
        created_at=job.created_at,
        application_count=job.application_count,
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
        skills=_skill_responses(published.skills),
        work_mode=published.work_mode,
        closing_date=published.closing_date,
        status=published.status,
        published_at=published.published_at,
        created_at=published.created_at,
    )


@router.get("/me", response_model=list[JobSummaryResponse])
def read_my_jobs(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> list[JobSummaryResponse]:
    response.headers["Cache-Control"] = "no-store"
    jobs = list_my_jobs(session, company_id=user.id)
    return [_to_summary_response(job) for job in jobs]


@router.patch(
    "/{job_id}",
    response_model=JobResponse,
    responses={code: PROBLEM_RESPONSE for code in (404,)},
)
def edit_job(
    job_id: UUID,
    request: UpdateJobRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> JobResponse:
    response.headers["Cache-Control"] = "no-store"
    updated = update_job(job_id, request, session=session, company_id=user.id)
    return _to_job_response(updated)


@router.patch(
    "/{job_id}/status",
    response_model=JobResponse,
    responses={code: PROBLEM_RESPONSE for code in (404, 409)},
)
def edit_job_status(
    job_id: UUID,
    request: UpdateJobStatusRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> JobResponse:
    response.headers["Cache-Control"] = "no-store"
    updated = change_job_status(job_id, request, session=session, company_id=user.id)
    return _to_job_response(updated)
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
