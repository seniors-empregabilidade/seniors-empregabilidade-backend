from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.db.models.enums import JobStatus, WorkMode
from app.skills.services import CatalogSkill


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    id: UUID
    company_id: UUID
    title: str
    description: str
    skills: list[CatalogSkill]
    work_mode: WorkMode
    closing_date: date
    status: JobStatus
    published_at: datetime
    created_at: datetime
