from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import TrainingMode
from app.skills.schemas import SkillResponse


class TrainingResponse(BaseModel):
    id: UUID
    title: str
    institution: str | None
    mode: TrainingMode | None
    external_link: str
    published: bool
    skills: list[SkillResponse]
    job_ids: list[UUID]
