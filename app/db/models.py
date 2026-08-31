from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserType(StrEnum):
    CANDIDATE = "candidate"
    COMPANY = "company"
    ADMINISTRATOR = "administrator"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class CompanyStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class SkillType(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class EmploymentStatus(StrEnum):
    EMPLOYED = "employed"
    UNEMPLOYED = "unemployed"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class WorkMode(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


class JobStatus(StrEnum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    PUBLISHED = "published"
    PAUSED = "paused"
    EXPIRED = "expired"
    CLOSED = "closed"


class JobOutcome(StrEnum):
    HIRED_ON_PLATFORM = "hired_on_platform"
    HIRED_ELSEWHERE = "hired_elsewhere"
    NOT_HIRED = "not_hired"
    CANCELLED = "cancelled"


class ApplicationType(StrEnum):
    ACTIVE = "active"
    AUTOMATIC = "automatic"


class ApplicationStatus(StrEnum):
    APPLIED = "applied"
    UNDER_REVIEW = "under_review"
    IN_SELECTION_PROCESS = "in_selection_process"
    HIRED = "hired"
    NOT_SELECTED = "not_selected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class TrainingMode(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    ONLINE = "online"


def enum_type(enum: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum, name=name, values_callable=lambda values: [v.value for v in values]
    )


class UUIDPrimaryKey:
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Timestamps(CreatedAt):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Address(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "address"

    street: Mapped[str] = mapped_column(String(150))
    number: Mapped[str] = mapped_column(String(10))
    complement: Mapped[str | None] = mapped_column(String(100))
    neighborhood: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(CHAR(2))
    zip_code: Mapped[str] = mapped_column(CHAR(8))
    code: Mapped[str | None] = mapped_column(String(20))


class Skill(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "skill"
    __table_args__ = (UniqueConstraint("name", "type"),)

    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[SkillType] = mapped_column(enum_type(SkillType, "skill_type"))


class AppUser(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    user_type: Mapped[UserType] = mapped_column(
        enum_type(UserType, "user_type"), index=True
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        enum_type(AccountStatus, "account_status"),
        server_default=AccountStatus.ACTIVE.value,
    )


class Candidate(Base):
    __tablename__ = "candidate"
    __table_args__ = (
        CheckConstraint(
            "birth_date <= CURRENT_DATE - INTERVAL '45 years'",
            name="minimum_age",
        ),
        CheckConstraint("age IS NULL OR age >= 45", name="age_value"),
        CheckConstraint("cpf ~ '^[0-9]{11}$'", name="cpf_format"),
    )

    id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        primary_key=True,
    )
    full_name: Mapped[str] = mapped_column(String(150))
    cpf: Mapped[str] = mapped_column(CHAR(11), unique=True)
    birth_date: Mapped[date] = mapped_column(Date)
    age: Mapped[int | None] = mapped_column(SmallInteger)
    phone: Mapped[str] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(CHAR(2))
    availability: Mapped[AvailabilityStatus] = mapped_column(
        enum_type(AvailabilityStatus, "availability_status"),
        server_default=AvailabilityStatus.AVAILABLE.value,
    )
    accepts_automatic_application: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    terms_version_accepted: Mapped[str | None] = mapped_column(String(20))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Resume(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "resume"
    __table_args__ = (
        CheckConstraint(
            "completion_percentage BETWEEN 0 AND 100", name="completion_percentage"
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "candidate.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        unique=True,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    employment_status: Mapped[EmploymentStatus | None] = mapped_column(
        enum_type(EmploymentStatus, "employment_status")
    )
    employment_status_since: Mapped[date | None] = mapped_column(Date)
    desired_salary: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    availability_start_date: Mapped[date | None] = mapped_column(Date)
    completion_percentage: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    skill_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), server_default=text("'{}'::uuid[]")
    )


class ResumeChild(UUIDPrimaryKey, Base):
    __abstract__ = True

    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "resume.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        index=True,
    )


class Experience(ResumeChild):
    __tablename__ = "experience"

    company_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(150))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)


class Education(ResumeChild):
    __tablename__ = "education"

    institution: Mapped[str] = mapped_column(String(150))
    degree: Mapped[str | None] = mapped_column(String(100))
    field: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)


class Certification(ResumeChild):
    __tablename__ = "certification"

    name: Mapped[str] = mapped_column(String(150))
    issuer: Mapped[str | None] = mapped_column(String(150))
    issued_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)


class Language(ResumeChild):
    __tablename__ = "language"

    name: Mapped[str] = mapped_column(String(60))
    proficiency: Mapped[str | None] = mapped_column(String(30))


class AttachedCertificate(ResumeChild):
    __tablename__ = "attached_certificate"

    file_url: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Company(Base):
    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint("cnpj ~ '^[0-9]{14}$'", name="cnpj_format"),
        CheckConstraint(
            "lower(split_part(corporate_email, '@', 2)) NOT IN "
            "('gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', "
            "'icloud.com', 'bol.com.br', 'uol.com.br')",
            name="corporate_email",
        ),
        Index("ix_company_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        primary_key=True,
    )
    cnpj: Mapped[str] = mapped_column(CHAR(14), unique=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    trade_name: Mapped[str | None] = mapped_column(String(200))
    primary_cnae: Mapped[str | None] = mapped_column(String(10))
    corporate_email: Mapped[str] = mapped_column(String(150), unique=True)
    corporate_email_confirmed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    company_size: Mapped[str | None] = mapped_column(String(30))
    industry: Mapped[str | None] = mapped_column(String(100))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    linkedin_verified: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "address.id",
            ondelete="SET NULL",
            deferrable=True,
            initially="IMMEDIATE",
        )
    )
    status: Mapped[CompanyStatus] = mapped_column(
        enum_type(CompanyStatus, "company_status"),
        server_default=CompanyStatus.PENDING.value,
    )
    terms_version_accepted: Mapped[str | None] = mapped_column(String(20))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Administrator(Base):
    __tablename__ = "administrator"

    id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        primary_key=True,
    )
    full_name: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Job(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "job"

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "company.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    work_mode: Mapped[WorkMode] = mapped_column(enum_type(WorkMode, "work_mode"))
    location: Mapped[str | None] = mapped_column(String(150))
    contract_type: Mapped[str | None] = mapped_column(String(50))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[JobStatus] = mapped_column(
        enum_type(JobStatus, "job_status"),
        server_default=JobStatus.DRAFT.value,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closing_date: Mapped[date] = mapped_column(Date)
    outcome: Mapped[JobOutcome | None] = mapped_column(
        enum_type(JobOutcome, "job_outcome")
    )
    featured: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    featured_until: Mapped[date | None] = mapped_column(Date)
    desired_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )


class Application(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id"),
        CheckConstraint("match_score BETWEEN 0 AND 100", name="match_score"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "candidate.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        index=True,
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "job.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        index=True,
    )
    type: Mapped[ApplicationType] = mapped_column(
        enum_type(ApplicationType, "application_type"),
        server_default=ApplicationType.ACTIVE.value,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus, "application_status"),
        server_default=ApplicationStatus.APPLIED.value,
    )
    match_score: Mapped[int | None] = mapped_column(SmallInteger)


class Training(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "training"

    title: Mapped[str] = mapped_column(String(150))
    provider: Mapped[str | None] = mapped_column(String(150))
    area: Mapped[str | None] = mapped_column(String(100))
    training_mode: Mapped[TrainingMode | None] = mapped_column(
        enum_type(TrainingMode, "training_mode")
    )
    workload_hours: Mapped[int | None] = mapped_column(SmallInteger)
    free: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    external_link: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), index=True
    )


class Event(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "event"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "app_user.id",
            ondelete="SET NULL",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Notification(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "notification"
    __table_args__ = (Index("ix_notification_user_id_read", "user_id", "read"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        )
    )
    type: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
