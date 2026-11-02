from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.skills.schemas import SkillResponse

TrimmedName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
TrimmedPhone = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=7, max_length=20)
]
TrimmedCity = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
TrimmedSummary = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000)
]
TrimmedState = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=2, max_length=2),
]


class ExperienceResponse(BaseModel):
    id: UUID
    role: str
    company_name: str
    start_date: date
    end_date: date | None = None
    description: str | None = None


class EducationResponse(BaseModel):
    id: UUID
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class CertificationDocumentResponse(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class CertificationResponse(BaseModel):
    id: UUID
    name: str
    issuer: str | None = None
    issued_date: date | None = None
    expiration_date: date | None = None
    document: CertificationDocumentResponse | None = None


class ProfessionalProfileResponse(BaseModel):
    id: UUID
    full_name: str
    age: int
    email: str
    phone: str
    city: str | None = None
    state: str | None = None
    summary: str | None = None
    accepts_automatic_application: bool = Field(
        description=(
            "Whether the professional allows the platform to apply on their behalf "
            "to compatible jobs (US-20). They can turn it off at any time."
        )
    )
    experiences: list[ExperienceResponse]
    education: list[EducationResponse]
    certifications: list[CertificationResponse]
    skills: list[SkillResponse]
    missing_fields: list[str]


class ProfessionalProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: TrimmedName | None = None
    phone: TrimmedPhone | None = None
    city: TrimmedCity | None = None
    state: TrimmedState | None = None
    summary: TrimmedSummary | None = None
    accepts_automatic_application: bool | None = None

    @field_validator("full_name", "phone", "accepts_automatic_application")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be cleared.")
        return value
