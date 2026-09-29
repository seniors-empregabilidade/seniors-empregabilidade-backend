from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import WorkMode
from app.skills.schemas import SkillResponse


class JobSearchResultResponse(BaseModel):
    id: UUID
    title: str
    company_name: str
    location: str | None
    work_mode: WorkMode
    salary_max: Decimal | None
    published_at: datetime | None
    days_since_published: int | None
    matched_skill_count: int
    required_skill_count: int
    missing_skills: list[SkillResponse]
