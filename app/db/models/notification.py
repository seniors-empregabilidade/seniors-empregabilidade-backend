from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey


class Notification(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "notification"
    __table_args__ = (Index("ix_notification_user_id_read", "user_id", "read"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        )
    )
    type: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
