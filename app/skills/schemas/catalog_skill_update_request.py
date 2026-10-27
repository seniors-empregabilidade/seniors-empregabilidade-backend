from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.db.models.enums import SkillType
from app.skills.schemas.catalog_skill_response import SkillStatus
from app.skills.schemas.skill import TypedSkillName


class CatalogSkillUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: TypedSkillName | None = None
    type: SkillType | None = None
    status: SkillStatus | None = None

    @model_validator(mode="after")
    def changes_something(self) -> Self:
        if self.name is None and self.type is None and self.status is None:
            raise ValueError("send at least one of name, type or status")
        return self
