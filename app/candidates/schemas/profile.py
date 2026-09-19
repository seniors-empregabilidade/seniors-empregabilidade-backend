from datetime import date
from uuid import UUID

from pydantic import BaseModel


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
