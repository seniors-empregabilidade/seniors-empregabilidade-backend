from dataclasses import dataclass
from uuid import UUID

from app.candidates.services.guidance_record import GuidanceRecord


@dataclass(frozen=True, slots=True)
class ProfessionalSummary:
    id: UUID
    full_name: str
    email: str
    phone: str
    city: str | None
    state: str | None
    missing_fields: tuple[str, ...]
    last_guidance: GuidanceRecord | None
