from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import Timestamps, UUIDPrimaryKey
from app.db.models.enums import EmploymentStatus, enum_type


class Resume(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "resume"
    __table_args__ = (
        CheckConstraint(
            "completion_percentage BETWEEN 0 AND 100", name="completion_percentage"
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "candidate.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
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
