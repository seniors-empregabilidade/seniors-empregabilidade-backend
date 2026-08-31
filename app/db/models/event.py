from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey


class Event(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "event"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "app_user.id", ondelete="SET NULL", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
