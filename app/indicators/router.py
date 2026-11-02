from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_administrator
from app.auth.schemas.current_user import CurrentUser
from app.core.csv_document import CSV_MEDIA_TYPE, csv_attachment
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    AvailabilityStatus,
    CompanyStatus,
    JobStatus,
)
from app.db.session import get_session
from app.indicators.schemas.indicator_filters import IndicatorFilters
from app.indicators.schemas.platform_indicators import PlatformIndicators
from app.indicators.services.export_indicators import export_indicators
from app.indicators.services.platform_indicators import get_platform_indicators

router = APIRouter(
    prefix="/indicators",
    tags=["indicators"],
    dependencies=[Depends(require_administrator)],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422, 503)},
)


def indicator_filters(
    start_date: Annotated[
        date | None,
        Query(description="First day of the period (America/Sao_Paulo, inclusive)."),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(description="Last day of the period (America/Sao_Paulo, inclusive)."),
    ] = None,
    account_status: Annotated[
        AccountStatus | None,
        Query(description="Restricts candidate and company accounts and live matches."),
    ] = None,
    candidate_availability: Annotated[
        AvailabilityStatus | None,
        Query(description="Restricts candidate-based indicators and live matches."),
    ] = None,
    company_status: Annotated[
        CompanyStatus | None,
        Query(description="Restricts the company count and live matches."),
    ] = None,
    job_status: Annotated[
        JobStatus | None,
        Query(description="Restricts the job count and live matches."),
    ] = None,
    application_status: Annotated[
        ApplicationStatus | None,
        Query(
            description="Restricts applications; potential matches need no application."
        ),
    ] = None,
) -> IndicatorFilters:
    return IndicatorFilters(
        start_date=start_date,
        end_date=end_date,
        account_status=account_status,
        candidate_availability=candidate_availability,
        company_status=company_status,
        job_status=job_status,
        application_status=application_status,
    )


@router.get("", response_model=PlatformIndicators)
def read_platform_indicators(
    session: Annotated[Session, Depends(get_session)],
    response: Response,
    filters: Annotated[IndicatorFilters, Depends(indicator_filters)],
) -> PlatformIndicators:
    response.headers["Cache-Control"] = "no-store"
    return get_platform_indicators(session, filters)


@router.get(
    "/export",
    response_class=Response,
    responses={
        200: {
            "content": {CSV_MEDIA_TYPE: {}},
            "description": "The applied filters and every indicator, as a CSV file.",
        }
    },
)
def export_platform_indicators(
    administrator: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[IndicatorFilters, Depends(indicator_filters)],
) -> Response:
    return csv_attachment(
        export_indicators(session, administrator_id=administrator.id, filters=filters)
    )
