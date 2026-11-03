"""Add contact_request to record company contacts with professionals.

US-29-T01 lets an approved company contact a professional listed for one of its
jobs. Each row records the company, the account that sent it, the professional,
the job, the message and the date. The professional is told through a
notification (US-26), whose e-mail copy and its result live in
``email_delivery``; no address of the professional is stored here.

Revision ID: 21585dd80658
Revises: c4a1d7e9b3f2
Create Date: 2026-10-26 23:23:31.593140+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "21585dd80658"
down_revision: str | Sequence[str] | None = "c4a1d7e9b3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_request",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("sent_by_user_id", sa.UUID(), nullable=True),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notification_id", sa.UUID(), nullable=False),
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(message)) BETWEEN 1 AND 2000",
            name=op.f("ck_contact_request_message_length"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("fk_contact_request_candidate_id_candidate"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            name=op.f("fk_contact_request_company_id_company"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
            name=op.f("fk_contact_request_job_id_job"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notification.id"],
            name=op.f("fk_contact_request_notification_id_notification"),
            ondelete="CASCADE",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["sent_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_contact_request_sent_by_user_id_app_user"),
            ondelete="SET NULL",
            initially="IMMEDIATE",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_request")),
        sa.UniqueConstraint(
            "notification_id", name=op.f("uq_contact_request_notification_id")
        ),
    )
    op.create_index(
        op.f("ix_contact_request_candidate_id"),
        "contact_request",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_contact_request_company_id_created_at",
        "contact_request",
        ["company_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_contact_request_job_id"), "contact_request", ["job_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_contact_request_job_id"), table_name="contact_request")
    op.drop_index(
        "ix_contact_request_company_id_created_at", table_name="contact_request"
    )
    op.drop_index(op.f("ix_contact_request_candidate_id"), table_name="contact_request")
    op.drop_table("contact_request")
