from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import UUIDPrimaryKey


class AttachedCertificate(UUIDPrimaryKey, Base):
    __tablename__ = "attached_certificate"

    certification_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "certification.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        unique=True,
    )
    object_key: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
