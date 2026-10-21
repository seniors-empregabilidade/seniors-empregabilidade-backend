from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import JobStatus, WorkMode
from app.skills.schemas import SkillResponse


class JobDetailResponse(BaseModel):
    id: UUID
    title: str
    description: str
    company_id: UUID
    company_name: str
    skills: list[SkillResponse]
    work_mode: WorkMode
    location: str | None
    closing_date: date
    status: JobStatus
    published_at: datetime | None
    already_applied: bool
    is_open: bool
    is_expired: bool
    is_applicable: bool
