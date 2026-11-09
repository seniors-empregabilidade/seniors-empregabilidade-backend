from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import TrainingMode
from app.trainings.schemas.training_fields import (
    ExternalLink,
    RelatedIds,
    TrainingInstitution,
    TrainingTitle,
)


class TrainingRequest(BaseModel):
    """A course as typed by an administrator.

    ``skill_ids`` and ``job_ids`` are the complete set of related records. A
    course stays hidden from candidates until it is published.
    """

    model_config = ConfigDict(extra="forbid")

    title: TrainingTitle
    institution: TrainingInstitution
    mode: TrainingMode
    external_link: ExternalLink
    published: bool = False
    skill_ids: RelatedIds = Field(default_factory=list)
    job_ids: RelatedIds = Field(default_factory=list)
