from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import CompanyStatus


class CompanyResponse(BaseModel):
    id: UUID
    email: str
    status: CompanyStatus
