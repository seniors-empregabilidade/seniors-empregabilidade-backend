from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import JobStatus, WorkMode
from app.skills.schemas import SkillResponse


class JobSummaryResponse(BaseModel):
    id: UUID
    title: str
    description: str
    skills: list[SkillResponse]
    work_mode: WorkMode
    closing_date: date
    status: JobStatus
    published_at: datetime
    created_at: datetime
    application_count: int
