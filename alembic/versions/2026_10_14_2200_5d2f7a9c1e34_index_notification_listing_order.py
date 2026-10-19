"""Index notifications by user in listing order.

US-26 lists a user's notifications newest first and paginates them by the
``(created_at, id)`` pair. Without this index every page sorted all of the
user's rows. ``ix_notification_user_id_read`` stays: it serves the unread count.

Revision ID: 5d2f7a9c1e34
Revises: b8c94551d715
Create Date: 2026-10-14 22:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d2f7a9c1e34"
down_revision: str | Sequence[str] | None = "b8c94551d715"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_notification_user_id_created_at_id",
        "notification",
        ["user_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_user_id_created_at_id", table_name="notification")
