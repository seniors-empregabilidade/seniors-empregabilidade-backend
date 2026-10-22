"""Add email_delivery for notification e-mails.

US-26-T02 sends an e-mail copy of selected notifications. Each row is written in
the same transaction as its notification and is sent afterwards, so a failed
e-mail never blocks the in-app notification. The recipient address is read from
``app_user`` at send time and is not stored here.

Revision ID: 9e4b6c2d8a17
Revises: 2ee06058c78d
Create Date: 2026-10-19 21:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e4b6c2d8a17"
down_revision: str | Sequence[str] | None = "2ee06058c78d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

email_delivery_status = sa.Enum(
    "pending", "sent", "failed", name="email_delivery_status"
)


def upgrade() -> None:
    op.create_table(
        "email_delivery",
        sa.Column("notification_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            email_delivery_status,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=100), nullable=True),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notification.id"],
            name=op.f("fk_email_delivery_notification_id_notification"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_delivery")),
        sa.UniqueConstraint(
            "notification_id", name=op.f("uq_email_delivery_notification_id")
        ),
    )
    op.create_index(
        "ix_email_delivery_status_next_attempt_at",
        "email_delivery",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_delivery_status_next_attempt_at", table_name="email_delivery"
    )
    op.drop_table("email_delivery")
    email_delivery_status.drop(op.get_bind(), checkfirst=False)
