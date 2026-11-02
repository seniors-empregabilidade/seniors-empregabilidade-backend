from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import AccountStatus, CompanyStatus, UserType


class AccountSummaryResponse(BaseModel):
    missing_fields: list[str] | None = Field(
        default=None, description="US-08 missing résumé fields; null for companies."
    )
    id: UUID
    user_type: UserType
    email: str
    display_name: str | None = Field(
        description="Candidate full name, or the company trade or legal name."
    )
    account_status: AccountStatus
    company_status: CompanyStatus | None = Field(
        description="Approval situation of a company; `null` for candidates."
    )
    completion_percentage: int | None = Field(
        description="Résumé completion of a candidate; `null` for companies."
    )
    created_at: datetime
