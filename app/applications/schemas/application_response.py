from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import ApplicationStatus


class ApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID
    status: ApplicationStatus
    submitted_at: datetime
    matched_requirements: int
    total_requirements: int
