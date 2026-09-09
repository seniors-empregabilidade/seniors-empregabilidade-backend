from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey


class EmailVerificationRequest(UUIDPrimaryKey, CreatedAt, Base):
    """One row per verification code delivery, used to rate limit resends.

    Append-only: the cooldown reads the most recent row and the hourly allowance
    counts rows inside the window, so neither needs to mutate history. The code
    itself is never stored, because the provider owns it.
    """

    __tablename__ = "email_verification_request"
    __table_args__ = (
        Index(
            "ix_email_verification_request_user_id_created_at", "user_id", "created_at"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "app_user.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        )
    )
