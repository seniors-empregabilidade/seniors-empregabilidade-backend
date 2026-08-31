from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import UUIDPrimaryKey


class Certification(UUIDPrimaryKey, Base):
    __tablename__ = "certification"

    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "resume.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150))
    issuer: Mapped[str | None] = mapped_column(String(150))
    issued_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
