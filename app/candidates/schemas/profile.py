from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

TrimmedName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
TrimmedPhone = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=7, max_length=20)
]
TrimmedCity = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
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


class ProfessionalProfileResponse(BaseModel):
    id: UUID
    full_name: str
    age: int
    email: str
    phone: str
    city: str | None = None
    state: str | None = None
    summary: str | None = None
    photo_url: str | None = None
    experiences: list[ExperienceResponse]
    education: list[EducationResponse]
    skills: list[str]


class ProfessionalProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: TrimmedName | None = None
    phone: TrimmedPhone | None = None
    city: TrimmedCity | None = None
    state: TrimmedState | None = None
    summary: str | None = None
