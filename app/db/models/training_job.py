from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey


class TrainingJob(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "training_job"
    __table_args__ = (UniqueConstraint("training_id", "job_id"),)

    training_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "training.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        )
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "job.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
    )
