"""merge skill catalog and main migration histories

Revision ID: 9b83337775e5
Revises: 54c377e37cc1, 753757edc4f5
Create Date: 2026-10-19 22:36:14.666253+00:00

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9b83337775e5"
down_revision: str | Sequence[str] | None = ("54c377e37cc1", "753757edc4f5")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
