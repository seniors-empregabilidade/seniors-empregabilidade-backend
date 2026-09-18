import os
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.db.session import get_engine


@pytest.fixture
def database_session() -> Iterator[Session]:
    if os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1":
        pytest.skip("requires RUN_DATABASE_INTEGRATION_TESTS=1 and PostgreSQL")

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()
