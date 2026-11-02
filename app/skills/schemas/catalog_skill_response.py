from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.db.models import Skill
from app.db.models.enums import SkillType

SkillStatus = Literal["active", "inactive"]


class CatalogSkillResponse(BaseModel):
    id: UUID
    name: str
    type: SkillType
    status: SkillStatus

    @classmethod
    def of(cls, skill: Skill) -> CatalogSkillResponse:
        return cls(
            id=skill.id,
            name=skill.name,
            type=skill.type,
            status="active" if skill.is_active else "inactive",
        )
