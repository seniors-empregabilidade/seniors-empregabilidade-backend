from uuid import UUID

from pydantic import BaseModel

from app.candidates.schemas.guidance import GuidanceResponse


class ProfessionalSummaryResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone: str
    city: str | None
    state: str | None
    missing_fields: list[str]
    last_guidance: GuidanceResponse | None
