from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import Timestamps, UUIDPrimaryKey


class ResumeSkill(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "resume_skill"
    __table_args__ = (UniqueConstraint("resume_id", "skill_id"),)

    resume_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "resume.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        )
    )
    skill_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "skill.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        )
    )
