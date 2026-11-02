from dataclasses import dataclass
from datetime import date

from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    AvailabilityStatus,
    CompanyStatus,
    JobStatus,
)


@dataclass(frozen=True)
class IndicatorFilters:
    """Filters accepted by the platform indicators; every field is optional."""

    start_date: date | None = None
    end_date: date | None = None
    account_status: AccountStatus | None = None
    candidate_availability: AvailabilityStatus | None = None
    company_status: CompanyStatus | None = None
    job_status: JobStatus | None = None
    application_status: ApplicationStatus | None = None
