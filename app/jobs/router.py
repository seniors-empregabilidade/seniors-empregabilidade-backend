from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_approved_company, require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_OFFSET, MAX_PAGE_SIZE
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.jobs.schemas import (
    CreateJobRequest,
    JobDetailResponse,
    JobResponse,
    JobSearchResultResponse,
    JobSummaryResponse,
    UpdateJobRequest,
    UpdateJobStatusRequest,
)
from app.jobs.schemas.job_applicants_response import (
    ApplicantProfileResponse,
    CompatibilitySkillResponse,
    JobApplicantResponse,
    JobApplicantsSummaryResponse,
)
from app.jobs.services import (
    JobRecord,
    JobSummary,
    change_job_status,
    get_job_detail,
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

MAX_SEARCH_LENGTH = 150

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
    "/{job_id}",
    response_model=JobDetailResponse,
    responses={code: PROBLEM_RESPONSE for code in (404,)},
)
def read_job_detail(
    job_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
) -> JobDetailResponse:
    """Full job data plus the calling candidate's application state.

    `is_applicable` is false for a job that is not open (closed, paused, expired
    or past its closing date) or that the candidate already applied to.
    """
    response.headers["Cache-Control"] = "no-store"
    detail = get_job_detail(session, job_id=job_id, candidate_id=user.id)
    return JobDetailResponse(
        id=detail.id,
        title=detail.title,
        description=detail.description,
        company_id=detail.company_id,
        company_name=detail.company_name,
        skills=[
            SkillResponse(id=skill.id, name=skill.name, type=skill.type)
            for skill in detail.skills
        ],
        work_mode=detail.work_mode,
        location=detail.location,
        closing_date=detail.closing_date,
        status=detail.status,
        published_at=detail.published_at,
        already_applied=detail.already_applied,
        is_open=detail.is_open,
        is_expired=detail.is_expired,
        is_applicable=detail.is_applicable,
    )


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
    """List a company job's applicants and automatic matches, ranked by compatibility.

    Returns an aggregate header (applicant, full-match and automatic-match counts)
    plus one list ordered by compatibility percentage (descending). Each row has
    an ``origin``: ``application`` for a professional who applied, or
    ``automatic_match`` for a compatible profile (50% or more) that has not.
    Only the company that owns the job can call this endpoint; a job from another
    company is returned as 404.
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
        automatic_match_count=summary.automatic_match_count,
        applicants=[_job_applicant_response(a) for a in summary.applicants],
    )


def _job_applicant_response(applicant: JobApplicant) -> JobApplicantResponse:
    return JobApplicantResponse(
        origin=applicant.origin,
        application_id=applicant.application_id,
        status=applicant.status,
        match_score=applicant.match_score,
        compatibility_percentage=applicant.compatibility_percentage,
        is_highlighted=applicant.is_highlighted,
        matched_skill_count=applicant.matched_skill_count,
        required_skill_count=applicant.required_skill_count,
        matched_skills=[
            CompatibilitySkillResponse(id=skill.id, name=skill.name)
            for skill in applicant.matched_skills
        ],
        missing_skills=[
            CompatibilitySkillResponse(id=skill.id, name=skill.name)
            for skill in applicant.missing_skills
        ],
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
