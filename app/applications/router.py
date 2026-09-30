from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.applications.schemas.application_action_response import (
    ApplicationActionResponse,
)
from app.applications.schemas.application_response import ApplicationResponse
from app.applications.schemas.application_summary_response import (
    ApplicationSummaryResponse,
)
from app.applications.schemas.create_application_request import (
    CreateApplicationRequest,
)
from app.applications.schemas.similar_job_response import SimilarJobResponse
from app.applications.schemas.update_application_status_request import (
    UpdateApplicationStatusRequest,
)
from app.applications.services.application_action_result import ApplicationActionResult
from app.applications.services.application_summary import ApplicationSummary
from app.applications.services.list_my_applications import list_my_applications
from app.applications.services.submit_application import (
    SubmittedApplication,
    submit_application,
)
from app.applications.services.update_application_status import (
    update_application_status,
)
from app.applications.services.withdraw_application import withdraw_application
from app.auth.dependencies import require_approved_company, require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session

router = APIRouter(
    prefix="/applications",
    tags=["applications"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403)},
)


def _to_response(summary: ApplicationSummary) -> ApplicationSummaryResponse:
    return ApplicationSummaryResponse(
        id=summary.id,
        job_id=summary.job_id,
        job_title=summary.job_title,
        company_name=summary.company_name,
        submitted_at=summary.submitted_at,
        days_in_process=summary.days_in_process,
        status=summary.status,
        similar_jobs=[
            SimilarJobResponse(
                id=job.id, title=job.title, company_name=job.company_name
            )
            for job in summary.similar_jobs
        ],
    )


def _to_application_response(submitted: SubmittedApplication) -> ApplicationResponse:
    return ApplicationResponse(
        id=submitted.id,
        job_id=submitted.job_id,
        status=submitted.status,
        submitted_at=submitted.submitted_at,
        matched_requirements=submitted.matched_requirements,
        total_requirements=submitted.total_requirements,
    )


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=201,
    responses={code: PROBLEM_RESPONSE for code in (404, 409, 422)},
)
def create_application(
    request: CreateApplicationRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationResponse:
    response.headers["Cache-Control"] = "no-store"
    submitted = submit_application(session, job_id=request.job_id, candidate_id=user.id)
    return _to_application_response(submitted)


def _action_to_response(result: ApplicationActionResult) -> ApplicationActionResponse:
    return ApplicationActionResponse(
        application_id=result.application_id,
        job_id=result.job_id,
        candidate_id=result.candidate_id,
        status=result.status,
        updated_at=result.updated_at,
    )


@router.get("/me", response_model=list[ApplicationSummaryResponse])
def read_my_applications(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    company_name: Annotated[
        str | None,
        Query(min_length=1, max_length=200, description="Partial company name filter"),
    ] = None,
) -> list[ApplicationSummaryResponse]:
    response.headers["Cache-Control"] = "no-store"
    summaries = list_my_applications(
        session, candidate_id=user.id, company_name=company_name
    )
    return [_to_response(summary) for summary in summaries]


@router.post(
    "/{application_id}/withdraw",
    response_model=ApplicationSummaryResponse,
    responses={code: PROBLEM_RESPONSE for code in (404, 409)},
)
def withdraw_my_application(
    application_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationSummaryResponse:
    response.headers["Cache-Control"] = "no-store"
    summary = withdraw_application(
        session, application_id=application_id, candidate_id=user.id
    )
    return _to_response(summary)


@router.patch(
    "/{application_id}/status",
    response_model=ApplicationActionResponse,
    responses={code: PROBLEM_RESPONSE for code in (404, 409)},
)
def update_my_application_status(
    application_id: UUID,
    request: UpdateApplicationStatusRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> ApplicationActionResponse:
    """Move a candidate's application to the next status.

    Only the company that owns the job the application belongs to can act on
    it. Allowed transitions::

        applied → under_review
        under_review → in_selection_process | not_selected
        in_selection_process → hired | not_selected

    When setting ``not_selected``, ``reason`` is required and will be shown
    to the candidate (US-13). Applications already in a terminal status
    (hired, not_selected, withdrawn, expired) respond with 409.
    """
    response.headers["Cache-Control"] = "no-store"
    result = update_application_status(
        session,
        application_id=application_id,
        company_id=user.id,
        request=request,
    )
    return _action_to_response(result)
