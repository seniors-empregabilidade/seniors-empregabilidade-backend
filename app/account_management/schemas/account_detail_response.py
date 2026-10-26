from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import AccountStatus, CompanyStatus, UserType


class AccountExperienceResponse(BaseModel):
    id: UUID
    role: str
    company_name: str
    start_date: date
    end_date: date | None = None


class AccountEducationResponse(BaseModel):
    id: UUID
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class AccountSkillResponse(BaseModel):
    id: UUID
    name: str


class AccountDetailResponse(BaseModel):
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
    application_count: int | None = Field(
        description="How many applications the candidate has submitted; `null` for companies."
    )
    summary: str | None = Field(
        description="Résumé summary; `null` when the candidate has none or the account is a company."
    )
    experiences: list[AccountExperienceResponse]
    education: list[AccountEducationResponse]
    skills: list[AccountSkillResponse]
    legal_name: str | None = Field(
        description="Company legal name; `null` for a candidate."
    )
    trade_name: str | None = Field(
        description="Company trade name; `null` when unset or the account is a candidate."
    )
    cnpj: str | None = Field(description="Company CNPJ; `null` for a candidate.")
    corporate_email: str | None = Field(
        description="Company corporate email; `null` for a candidate."
    )
    city: str | None = Field(
        description="Company city; `null` when it has no address or the account is a candidate."
    )
    state: str | None = Field(
        description="Company state code; `null` when it has no address or the account is a candidate."
    )
    industry: str | None = Field(
        description="Company industry; `null` when unset or the account is a candidate."
    )
    company_size: str | None = Field(
        description="Company size; `null` when unset or the account is a candidate."
    )
    published_job_count: int | None = Field(
        description="Jobs the company currently has published; `null` for a candidate."
    )
