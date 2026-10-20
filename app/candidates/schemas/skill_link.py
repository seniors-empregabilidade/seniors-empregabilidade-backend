from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_SELECTED_SKILLS = 100


class SkillLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: UUID


class SkillSelectionRequest(BaseModel):
    """The whole set of catalog skills a professional keeps on the résumé."""

    model_config = ConfigDict(extra="forbid")

    skill_ids: Annotated[list[UUID], Field(max_length=MAX_SELECTED_SKILLS)]
