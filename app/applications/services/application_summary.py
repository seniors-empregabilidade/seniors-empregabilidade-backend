from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.applications.services.find_similar_jobs import SimilarJob
from app.db.models.enums import ApplicationStatus


@dataclass(frozen=True, slots=True)
class ApplicationSummary:
    """Output shared by `list_my_applications` and `withdraw_application`.

    This is an application-layer value, not an HTTP DTO: it carries no
    Pydantic/FastAPI dependency. `app/applications/router.py` maps it to
    `ApplicationSummaryResponse` for the public contract.
    """

    id: UUID
    job_id: UUID
    job_title: str
    company_name: str
    submitted_at: datetime
    days_in_process: int
    status: ApplicationStatus
    similar_jobs: list[SimilarJob] = field(default_factory=list)
