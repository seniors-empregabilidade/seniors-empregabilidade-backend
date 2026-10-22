from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import ApplicationStatus
from app.jobs.domain.candidate_origin import CandidateOrigin


class ApplicantProfileResponse(BaseModel):
    candidate_id: UUID
    full_name: str
    city: str | None
    state: str | None


class JobApplicantResponse(BaseModel):
    origin: Annotated[
        CandidateOrigin,
        Field(
            description=(
                "application: the professional applied to the job. automatic_match: "
                "a compatible profile (50% or more) that has not applied. The origin "
                "never changes compatibility_percentage."
            )
        ),
    ]
    application_id: Annotated[
        UUID | None, Field(description="Null for an automatic match.")
    ]
    status: Annotated[
        ApplicationStatus | None, Field(description="Null for an automatic match.")
    ]
    match_score: Annotated[
        int | None, Field(description="Null for an automatic match.")
    ]
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
    total_applicant_count: Annotated[
        int, Field(description="Applications to the job; automatic matches excluded.")
    ]
    full_match_count: Annotated[
        int, Field(description="Applicants who have every required skill.")
    ]
    automatic_match_count: Annotated[
        int, Field(description="Compatible profiles listed without an application.")
    ]
    applicants: list[JobApplicantResponse]
