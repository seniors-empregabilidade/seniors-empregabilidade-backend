from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey
from app.db.models.enums import EmailDeliveryStatus, enum_type
from app.db.models.notification import Notification


class EmailDelivery(UUIDPrimaryKey, CreatedAt, Base):
    """E-mail copy of one notification, written in the notification's transaction.

    The recipient address is not stored: it is read from `app_user` when the
    message is sent, so this table holds no personal data of its own.
    """

    __tablename__ = "email_delivery"
    __table_args__ = (
        Index("ix_email_delivery_status_next_attempt_at", "status", "next_attempt_at"),
    )

    notification_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "notification.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        unique=True,
    )
    status: Mapped[EmailDeliveryStatus] = mapped_column(
        enum_type(EmailDeliveryStatus, "email_delivery_status"),
        server_default=EmailDeliveryStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A provider error code such as `MessageRejected`, never a message text.
    last_error: Mapped[str | None] = mapped_column(String(100))

    # Lets the unit of work insert the notification before this row.
    notification: Mapped[Notification] = relationship()
