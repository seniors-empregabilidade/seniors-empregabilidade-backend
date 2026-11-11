from pydantic import BaseModel, Field

from app.jobs.schemas.admin_job_response import AdminJobResponse


class AdminJobListResponse(BaseModel):
    items: list[AdminJobResponse]
    total: int = Field(description="Every job matching the search.")
