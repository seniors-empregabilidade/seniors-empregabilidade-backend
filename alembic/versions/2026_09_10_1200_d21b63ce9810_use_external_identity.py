"""Replace local passwords with an external identity subject.

Revision ID: d21b63ce9810
Revises: b7de57d19d14
"""

import sqlalchemy as sa

from alembic import op

revision = "d21b63ce9810"
down_revision = "b7de57d19d14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_user", sa.Column("identity_subject", sa.String(255), nullable=True)
    )
    op.create_unique_constraint(
        "uq_app_user_identity_subject", "app_user", ["identity_subject"]
    )
    op.create_check_constraint(
        "identity_subject_not_blank",
        "app_user",
        "identity_subject IS NULL OR length(trim(identity_subject)) > 0",
    )
    op.drop_column("app_user", "password_hash")


def downgrade() -> None:
    # Passwords cannot be recovered from a provider subject. Never invent credentials.
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM app_user)")):
        raise RuntimeError(
            "Cannot restore local passwords for existing users; downgrade requires an empty app_user table."
        )
    op.add_column("app_user", sa.Column("password_hash", sa.Text(), nullable=False))
    op.drop_constraint(
        op.f("ck_app_user_identity_subject_not_blank"), "app_user", type_="check"
    )
    op.drop_constraint("uq_app_user_identity_subject", "app_user", type_="unique")
    op.drop_column("app_user", "identity_subject")
