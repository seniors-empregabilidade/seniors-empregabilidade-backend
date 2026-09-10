from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import CompanyStatus, UserType


class CurrentUser(BaseModel):
    id: UUID
    user_type: UserType
    company_status: CompanyStatus | None = None
