from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import AvailabilityStatus, enum_type


class Candidate(Base):
    __tablename__ = "candidate"
    __table_args__ = (
        CheckConstraint(
            "birth_date <= CURRENT_DATE - INTERVAL '45 years'", name="minimum_age"
        ),
        CheckConstraint("age IS NULL OR age >= 45", name="age_value"),
        CheckConstraint("cpf ~ '^[0-9]{11}$'", name="cpf_format"),
    )

    id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
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
