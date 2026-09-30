from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import ApplicationStatus


class ApplicationActionResponse(BaseModel):
    application_id: UUID
    job_id: UUID
    candidate_id: UUID
    status: ApplicationStatus
    updated_at: datetime
