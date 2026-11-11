from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import JobStatus


class AdminJobResponse(BaseModel):
    """A job as an administrator picks it, for example to relate a course."""

    id: UUID
    title: str
    company_name: str
    status: JobStatus
