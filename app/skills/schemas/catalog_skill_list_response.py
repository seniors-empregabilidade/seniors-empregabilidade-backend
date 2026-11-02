from pydantic import BaseModel, Field

from app.skills.schemas.catalog_skill_response import CatalogSkillResponse


class CatalogSkillListResponse(BaseModel):
    items: list[CatalogSkillResponse]
    total: int = Field(description="Every catalog skill matching the filters.")
