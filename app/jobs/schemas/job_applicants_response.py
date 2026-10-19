from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import ApplicationStatus


class ApplicantProfileResponse(BaseModel):
    candidate_id: UUID
    full_name: str
    city: str | None
    state: str | None


class JobApplicantResponse(BaseModel):
    application_id: UUID
    status: ApplicationStatus
    match_score: int | None
    compatibility_percentage: Annotated[
        Decimal | None,
        Field(
            description=(
                "Required skills on the résumé / required skills * 100, two decimal "
                "places. Null when the job has no required skills."
            )
        ),
    ]
    is_highlighted: Annotated[
        bool, Field(description="True when the compatibility is 50% or more.")
    ]
    matched_skill_count: int
    required_skill_count: int
    profile: ApplicantProfileResponse


class JobApplicantsSummaryResponse(BaseModel):
    job_id: UUID
    total_applicant_count: int
    full_match_count: int
    applicants: list[JobApplicantResponse]
