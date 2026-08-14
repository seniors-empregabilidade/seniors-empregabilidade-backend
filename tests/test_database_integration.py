import os

import pytest

from app.db.session import is_database_ready


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
    reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and PostgreSQL",
)
def test_database_probe_against_postgresql() -> None:
    assert is_database_ready() is True
