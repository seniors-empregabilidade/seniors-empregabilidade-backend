from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Administrator(Base):
    __tablename__ = "administrator"

    id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        primary_key=True,
    )
    full_name: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
