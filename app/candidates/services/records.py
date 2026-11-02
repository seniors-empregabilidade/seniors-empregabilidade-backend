from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.db.models.attached_certificate import AttachedCertificate
from app.db.models.certification import Certification
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
class CertificationDocumentRecord:
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


@dataclass(frozen=True, slots=True)
class CertificationRecord:
    id: UUID
    name: str
    issuer: str | None
    issued_date: date | None
    expiration_date: date | None
    document: CertificationDocumentRecord | None


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
    accepts_automatic_application: bool
    experiences: tuple[ExperienceRecord, ...]
    education: tuple[EducationRecord, ...]
    certifications: tuple[CertificationRecord, ...]
    skills: tuple[CatalogSkill, ...]
    missing_fields: tuple[str, ...]


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


def certification_record(
    certification: Certification, document: AttachedCertificate | None
) -> CertificationRecord:
    return CertificationRecord(
        id=certification.id,
        name=certification.name,
        issuer=certification.issuer,
        issued_date=certification.issued_date,
        expiration_date=certification.expiration_date,
        document=CertificationDocumentRecord(
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            uploaded_at=document.uploaded_at,
        )
        if document is not None
        else None,
    )
