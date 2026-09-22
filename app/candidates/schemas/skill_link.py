from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SkillLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
