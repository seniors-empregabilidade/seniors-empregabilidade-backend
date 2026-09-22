from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.db.models.education import Education
from app.db.models.experience import Experience
from app.skills.services import CatalogSkill


@dataclass(frozen=True, slots=True)
class ExperienceRecord:
    id: UUID
    company_name: str
    role: str
    start_date: date
    end_date: date | None
    description: str | None


@dataclass(frozen=True, slots=True)
class EducationRecord:
    id: UUID
    institution: str
    degree: str | None
    field: str | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True, slots=True)
class ProfileRecord:
    id: UUID
    full_name: str
    age: int
    email: str
    phone: str
    city: str | None
    state: str | None
    summary: str | None
    experiences: tuple[ExperienceRecord, ...]
    education: tuple[EducationRecord, ...]
    skills: tuple[CatalogSkill, ...]


def experience_record(experience: Experience) -> ExperienceRecord:
    return ExperienceRecord(
        id=experience.id,
        company_name=experience.company_name,
        role=experience.role,
        start_date=experience.start_date,
        end_date=experience.end_date,
        description=experience.description,
    )


def education_record(education: Education) -> EducationRecord:
    return EducationRecord(
        id=education.id,
        institution=education.institution,
        degree=education.degree,
        field=education.field,
        start_date=education.start_date,
        end_date=education.end_date,
    )
