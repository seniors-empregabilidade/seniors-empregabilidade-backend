from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models.enums import JobStatus, WorkMode
from app.skills.schemas import SkillRequest, SkillResponse

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description = ""
    skills: Annotated[list[SkillRequest], Field(min_length=1, max_length=100)]
    work_mode: WorkMode
    closing_date: date


class UpdateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description = ""
    skills: Annotated[list[SkillRequest], Field(min_length=1, max_length=100)]


class JobResponse(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    description: str
    skills: list[SkillResponse]
    work_mode: WorkMode
    closing_date: date
    status: JobStatus
    published_at: datetime
    created_at: datetime
