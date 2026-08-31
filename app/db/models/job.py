from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import Timestamps, UUIDPrimaryKey
from app.db.models.enums import JobOutcome, JobStatus, WorkMode, enum_type


class Job(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "job"

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "company.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
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
