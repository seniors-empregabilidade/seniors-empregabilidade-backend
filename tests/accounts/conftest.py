import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models.app_user import AppUser
from app.db.session import get_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
    reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
)


class FakeEmailVerificationProvider:
    """In-memory stand-in for the external provider.

    Records what it was asked to send so tests can assert on delivery without
    reaching AWS, and can be told to fail to exercise the unavailable path.
    """

    def __init__(self) -> None:
        self.sent_to: list[str] = []
        self.confirmed: list[tuple[str, str]] = []
        self.failure: Exception | None = None

    def send_code(self, *, email: str) -> None:
        if self.failure is not None:
            raise self.failure
        self.sent_to.append(email)

    def confirm_code(self, *, email: str, code: str) -> None:
        if self.failure is not None:
            raise self.failure
        self.confirmed.append((email, code))


@pytest.fixture
def session() -> Iterator[Session]:
    """A session whose writes are always rolled back.

    The session joins an outer transaction and turns its own commits into
    savepoints, so a use case under test can commit normally while the test
    still leaves the database exactly as it found it.
    """
    connection = get_engine().connect()
    transaction = connection.begin()
    test_session = Session(
        bind=connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    yield test_session

    test_session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def provider() -> FakeEmailVerificationProvider:
    return FakeEmailVerificationProvider()


@pytest.fixture
def unverified_user(session: Session) -> AppUser:
    user = AppUser(
        email=f"{uuid4()}@example.invalid",
        password_hash="not-a-real-hash",
        user_type="candidate",
    )
    session.add(user)
    session.flush()
    return user
