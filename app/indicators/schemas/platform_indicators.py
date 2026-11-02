from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    AvailabilityStatus,
    CompanyStatus,
    JobStatus,
)


class AppliedFilters(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_date: date | None
    end_date: date | None
    account_status: AccountStatus | None
    candidate_availability: AvailabilityStatus | None
    company_status: CompanyStatus | None
    job_status: JobStatus | None
    application_status: ApplicationStatus | None


class IndicatorTotals(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: int = Field(ge=0)
    companies: int = Field(ge=0)
    jobs: int = Field(ge=0)
    applications: int = Field(ge=0)
    matches: int = Field(ge=0)


class IndicatorSegments(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates_without_placement: int = Field(ge=0)
    candidates_with_unknown_employment: int = Field(ge=0)
    incomplete_resumes: int = Field(ge=0)


class PlatformIndicators(BaseModel):
    model_config = ConfigDict(frozen=True)

    filters: AppliedFilters
    totals: IndicatorTotals
    segments: IndicatorSegments
