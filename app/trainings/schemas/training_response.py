from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import TrainingMode
from app.skills.schemas import SkillResponse
from app.trainings.schemas.training_job_response import TrainingJobResponse


class TrainingResponse(BaseModel):
    id: UUID
    title: str
    institution: str | None
    mode: TrainingMode | None
    external_link: str
    published: bool
    skills: list[SkillResponse]
    job_ids: list[UUID]
    jobs: list[TrainingJobResponse]
