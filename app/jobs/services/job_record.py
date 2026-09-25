from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.db.models import Job
from app.db.models.enums import JobStatus, WorkMode
from app.skills.services import CatalogSkill


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: UUID
    company_id: UUID
    title: str
    description: str
    skills: list[CatalogSkill]
    work_mode: WorkMode
    closing_date: date
    status: JobStatus
    published_at: datetime | None
    created_at: datetime

    @classmethod
    def of(cls, job: Job, skills: Sequence[CatalogSkill]) -> JobRecord:
        return cls(
            id=job.id,
            company_id=job.company_id,
            title=job.title,
            description=job.description,
            skills=list(skills),
            work_mode=job.work_mode,
            closing_date=job.closing_date,
            status=job.status,
            published_at=job.published_at,
            created_at=job.created_at,
        )
