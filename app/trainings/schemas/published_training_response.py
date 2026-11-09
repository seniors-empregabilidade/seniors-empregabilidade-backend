from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import TrainingMode
from app.skills.schemas import SkillResponse


class PublishedTrainingResponse(BaseModel):
    """A published course as candidates see it; related jobs stay private."""

    id: UUID
    title: str
    institution: str | None
    mode: TrainingMode | None
    external_link: str
    skills: list[SkillResponse]
