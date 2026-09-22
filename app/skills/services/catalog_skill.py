from dataclasses import dataclass
from uuid import UUID

from app.db.models import Skill
from app.db.models.enums import SkillType


@dataclass(frozen=True, slots=True)
class CatalogSkill:
    id: UUID
    name: str
    type: SkillType

    @classmethod
    def of(cls, skill: Skill) -> CatalogSkill:
        return cls(id=skill.id, name=skill.name, type=skill.type)
