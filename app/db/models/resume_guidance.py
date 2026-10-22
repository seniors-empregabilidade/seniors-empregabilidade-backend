from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey


class ResumeGuidance(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "resume_guidance"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(note)) BETWEEN 1 AND 2000", name="note_length"
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="CASCADE", deferrable=True),
        nullable=False,
    )
    administrator_id: Mapped[UUID] = mapped_column(
        ForeignKey("administrator.id", ondelete="RESTRICT", deferrable=True),
        nullable=False,
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)


Index(
    "ix_resume_guidance_candidate_id_created_at_id",
    ResumeGuidance.candidate_id,
    ResumeGuidance.created_at.desc(),
    ResumeGuidance.id.desc(),
)
