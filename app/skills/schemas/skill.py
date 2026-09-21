from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.db.models.enums import SkillType
from app.skills.domain import MAX_SKILL_NAME_LENGTH, InvalidSkillNameError, SkillName


def _comparable_with_the_catalog(name: str) -> str:
    try:
        SkillName.parse(name)
    except InvalidSkillNameError as exc:
        raise ValueError(
            "skill name must have visible characters, no control characters, and at "
            f"most {MAX_SKILL_NAME_LENGTH} characters once case and accents are removed"
        ) from exc
    return name


TypedSkillName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_SKILL_NAME_LENGTH
    ),
    AfterValidator(_comparable_with_the_catalog),
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
