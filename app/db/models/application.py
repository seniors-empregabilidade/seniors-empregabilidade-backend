from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import Timestamps, UUIDPrimaryKey
from app.db.models.enums import ApplicationStatus, ApplicationType, enum_type


class Application(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id"),
        CheckConstraint("match_score BETWEEN 0 AND 100", name="match_score"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "candidate.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "job.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
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
