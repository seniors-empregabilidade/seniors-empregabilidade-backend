from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import UUIDPrimaryKey


class Language(UUIDPrimaryKey, Base):
    __tablename__ = "language"

    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "resume.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(60))
    proficiency: Mapped[str | None] = mapped_column(String(30))
