from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import UUIDPrimaryKey


class AttachedCertificate(UUIDPrimaryKey, Base):
    __tablename__ = "attached_certificate"

    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "resume.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
    )
    file_url: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
