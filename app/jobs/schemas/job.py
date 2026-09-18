from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models.enums import JobStatus

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description = ""
    skill_ids: Annotated[list[UUID], Field(min_length=1)]


class JobResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    description: str
    skill_ids: list[UUID]
    status: JobStatus
    published_at: datetime
    created_at: datetime
