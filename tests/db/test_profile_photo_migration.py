"""Integration test for the profile photo migration.

Verifies that ``upgrade head`` adds the five nullable photo columns to both
``candidate`` and ``company``, and that ``downgrade -1`` removes them cleanly.

Requires a running PostgreSQL instance and the schema already migrated to
3a7c5e9d1b24 (the revision immediately before the photo columns).
"""

import os

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from app.db.session import get_engine


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    return cfg


PHOTO_COLUMNS = {
    "photo_object_key",
    "photo_filename",
    "photo_content_type",
    "photo_size_bytes",
    "photo_uploaded_at",
}

PHOTO_REVISION = "9466fd3b08cf"
PREV_REVISION = "3a7c5e9d1b24"


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
    reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
)
def test_photo_columns_present_after_upgrade() -> None:
    """After upgrade head the five photo columns exist on both tables and are nullable."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    engine = get_engine()
    inspector = inspect(engine)

    for table in ("candidate", "company"):
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        for col_name in PHOTO_COLUMNS:
            assert col_name in cols, f"{col_name} missing from {table}"
            assert cols[col_name]["nullable"] is True, (
                f"{col_name} on {table} should be nullable"
            )


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
    reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
)
def test_photo_columns_absent_after_downgrade() -> None:
    """After downgrade -1 the five photo columns are removed from both tables."""
    cfg = _alembic_config()

    # Ensure we start from head, then downgrade one step.
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")

    engine = get_engine()
    inspector = inspect(engine)

    for table in ("candidate", "company"):
        col_names = {c["name"] for c in inspector.get_columns(table)}
        for col_name in PHOTO_COLUMNS:
            assert col_name not in col_names, (
                f"{col_name} should have been removed from {table} after downgrade"
            )

    # Restore head so the database is left in the correct state.
    command.upgrade(cfg, "head")


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
    reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
)
def test_photo_columns_version_after_upgrade() -> None:
    """After upgrade the alembic version matches the photo revision."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar_one()

    assert version == PHOTO_REVISION
