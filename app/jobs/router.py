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
    JobSearchResultResponse,
    JobSummaryResponse,
    UpdateJobRequest,
    UpdateJobStatusRequest,
)
from app.jobs.schemas.job_applicants_response import (
    ApplicantProfileResponse,
    JobApplicantResponse,
    JobApplicantsSummaryResponse,
)
from app.jobs.services import (
    JobRecord,
    JobSummary,
    change_job_status,
    list_company_jobs,
    publish_job,
    search_jobs,
    update_job,
)
from app.jobs.services.list_job_applicants import (
    JobApplicant,
    JobApplicantsSummary,
    list_job_applicants,
)
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


@router.get("/me", response_model=list[JobSummaryResponse])
def read_my_jobs(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> list[JobSummaryResponse]:
    response.headers["Cache-Control"] = "no-store"
    return [
        _job_summary_response(summary)
        for summary in list_company_jobs(session=session, company_id=user.id)
    ]


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
    return _job_response(
        update_job(job_id, request, session=session, company_id=user.id)
    )


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
    return _job_response(
        change_job_status(job_id, request, session=session, company_id=user.id)
    )


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


@router.get(
    "/{job_id}/applications",
    response_model=JobApplicantsSummaryResponse,
    responses={code: PROBLEM_RESPONSE for code in (404,)},
)
def list_applicants(
    job_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> JobApplicantsSummaryResponse:
    """List candidates who applied to a company job, with skill-match data.

    Returns aggregate header (total and full-match count) plus a per-applicant
    list ordered by match (descending). Only the company that owns the job can
    call this endpoint; a job from another company is returned as 404.
    """
    response.headers["Cache-Control"] = "no-store"
    summary = list_job_applicants(session, job_id=job_id, company_id=user.id)
    return _job_applicants_summary_response(summary)


def _job_applicants_summary_response(
    summary: JobApplicantsSummary,
) -> JobApplicantsSummaryResponse:
    return JobApplicantsSummaryResponse(
        job_id=summary.job_id,
        total_applicant_count=summary.total_applicant_count,
        full_match_count=summary.full_match_count,
        applicants=[_job_applicant_response(a) for a in summary.applicants],
    )


def _job_applicant_response(applicant: JobApplicant) -> JobApplicantResponse:
    return JobApplicantResponse(
        application_id=applicant.application_id,
        status=applicant.status,
        match_score=applicant.match_score,
        matched_skill_count=applicant.matched_skill_count,
        required_skill_count=applicant.required_skill_count,
        profile=ApplicantProfileResponse(
            candidate_id=applicant.profile.candidate_id,
            full_name=applicant.profile.full_name,
            city=applicant.profile.city,
            state=applicant.profile.state,
        ),
    )


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


def _job_summary_response(summary: JobSummary) -> JobSummaryResponse:
    return JobSummaryResponse(
        **_job_response(summary.record).model_dump(),
        application_count=summary.application_count,
    )
