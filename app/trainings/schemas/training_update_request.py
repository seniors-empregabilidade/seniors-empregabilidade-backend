from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.db.models.enums import TrainingMode
from app.trainings.schemas.training_fields import (
    ExternalLink,
    RelatedIds,
    TrainingInstitution,
    TrainingTitle,
)


class TrainingUpdateRequest(BaseModel):
    """Changes to a course; omitted fields stay as they are.

    ``skill_ids`` and ``job_ids`` replace the whole set, so an empty list removes
    every relation of that kind.
    """

    model_config = ConfigDict(extra="forbid")

    title: TrainingTitle | None = None
    institution: TrainingInstitution | None = None
    mode: TrainingMode | None = None
    external_link: ExternalLink | None = None
    published: bool | None = None
    skill_ids: RelatedIds | None = None
    job_ids: RelatedIds | None = None

    @model_validator(mode="after")
    def changes_something(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("send at least one field to change")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
