from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import CompanyStatus, enum_type


class Company(Base):
    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint("cnpj ~ '^[0-9]{14}$'", name="cnpj_format"),
        CheckConstraint(
            "lower(split_part(corporate_email, '@', 2)) NOT IN ('gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'icloud.com', 'bol.com.br', 'uol.com.br')",
            name="corporate_email",
        ),
        Index("ix_company_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
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
            "address.id", ondelete="SET NULL", deferrable=True, initially="IMMEDIATE"
        )
    )
    status: Mapped[CompanyStatus] = mapped_column(
        enum_type(CompanyStatus, "company_status"),
        server_default=CompanyStatus.PENDING.value,
    )
    terms_version_accepted: Mapped[str | None] = mapped_column(String(20))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
