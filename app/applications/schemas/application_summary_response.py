from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.applications.schemas.similar_job_response import SimilarJobResponse
from app.db.models.enums import ApplicationStatus


class ApplicationSummaryResponse(BaseModel):
    id: UUID
    job_id: UUID
    job_title: str
    company_name: str
    submitted_at: datetime
    days_in_process: int
    status: ApplicationStatus
    similar_jobs: list[SimilarJobResponse] = Field(default_factory=list)
