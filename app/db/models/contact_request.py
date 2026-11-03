from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.common import CreatedAt, UUIDPrimaryKey
from app.db.models.notification import Notification


class ContactRequest(UUIDPrimaryKey, CreatedAt, Base):
    """A company's contact with a professional about one of its jobs (US-29).

    The row is the record of the contact: who sent it, to whom, about which job
    and when. The professional receives it as a notification; its e-mail copy
    and that copy's result live in `email_delivery`, reached through
    `notification_id`. No address of the professional is stored here.
    """

    __tablename__ = "contact_request"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(message)) BETWEEN 1 AND 2000", name="message_length"
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "company.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        nullable=False,
    )
    # The account that pressed "send". Today a company has a single account, so
    # it equals `company_id`; it is kept apart so the record stays correct if a
    # company ever has several users.
    sent_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "app_user.id", ondelete="SET NULL", deferrable=True, initially="IMMEDIATE"
        )
    )
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "candidate.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
        nullable=False,
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "job.id", ondelete="CASCADE", deferrable=True, initially="IMMEDIATE"
        ),
        index=True,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "notification.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        unique=True,
        nullable=False,
    )

    # Lets the unit of work insert the notification before this row.
    notification: Mapped[Notification] = relationship()


# Serves a company's contacts, newest first.
Index(
    "ix_contact_request_company_id_created_at",
    ContactRequest.company_id,
    ContactRequest.created_at.desc(),
)
