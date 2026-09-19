from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.db.models.enums import SkillType
from app.skills.domain import MAX_SKILL_NAME_LENGTH

TypedSkillName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_SKILL_NAME_LENGTH
    ),
]


class SkillRequest(BaseModel):
    """A skill as typed by a company or an administrator.

    The type classifies a skill that the catalog does not have yet; it is ignored
    when the name already identifies a catalog entry.
    """

    model_config = ConfigDict(extra="forbid")

    name: TypedSkillName
    type: SkillType


class SkillResponse(BaseModel):
    id: UUID
    name: str
    type: SkillType
