from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import CompanyStatus


class CompanyStatusResponse(BaseModel):
    id: UUID
    status: CompanyStatus
    rejection_reason: str | None
