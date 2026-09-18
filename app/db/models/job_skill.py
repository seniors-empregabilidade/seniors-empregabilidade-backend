from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import Timestamps, UUIDPrimaryKey


class JobSkill(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "job_skill"
    __table_args__ = (UniqueConstraint("job_id", "skill_id"),)

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("job.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE")
    )
    skill_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "skill.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        )
    )
