from enum import StrEnum

from sqlalchemy import Enum


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
