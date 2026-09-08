import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.auth.exceptions import AccountNotActiveError
from app.auth.services.authenticate_user import authenticate_user
from app.auth.services.identity_provider import IdentityTokens
from app.db.models.app_user import AppUser
from app.db.models.enums import AccountStatus, UserType
from app.db.session import get_session_factory
from tests.auth.conftest import FakeIdentityProvider

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
    reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
)

EMAIL = "integration-login@example.invalid"


@pytest.fixture
def session() -> Iterator[Session]:
    """Give each test a real session that is always rolled back."""
    with get_session_factory()() as active_session:
        try:
            yield active_session
        finally:
            active_session.rollback()
            active_session.execute(delete(AppUser).where(AppUser.email == EMAIL))
            active_session.commit()


def add_user(session: Session, status: AccountStatus) -> None:
    session.execute(
        insert(AppUser).values(
            id=uuid4(),
            email=EMAIL,
            # Cognito owns the password; this column is not consulted on sign-in.
            password_hash="not-used-by-cognito-authentication",
            user_type=UserType.COMPANY.value,
            account_status=status.value,
        )
    )
    session.flush()


@pytest.mark.integration
def test_the_query_reads_the_role_from_postgresql(
    session: Session, tokens: IdentityTokens
) -> None:
    add_user(session, AccountStatus.ACTIVE)

    result = authenticate_user(
        email=EMAIL,
        password="LocalDemoOnly!2026",
        session=session,
        identity_provider=FakeIdentityProvider(tokens=tokens),
    )

    assert result.user_type is UserType.COMPANY
    assert result.tokens is tokens


@pytest.mark.integration
@pytest.mark.parametrize("status", [AccountStatus.SUSPENDED, AccountStatus.BLOCKED])
def test_a_non_active_status_round_trips_and_blocks_sign_in(
    session: Session, tokens: IdentityTokens, status: AccountStatus
) -> None:
    add_user(session, status)

    with pytest.raises(AccountNotActiveError):
        authenticate_user(
            email=EMAIL,
            password="LocalDemoOnly!2026",
            session=session,
            identity_provider=FakeIdentityProvider(tokens=tokens),
        )


@pytest.mark.integration
def test_an_unknown_email_cannot_sign_in(
    session: Session, tokens: IdentityTokens
) -> None:
    with pytest.raises(AccountNotActiveError):
        authenticate_user(
            email="absent-from-database@example.invalid",
            password="LocalDemoOnly!2026",
            session=session,
            identity_provider=FakeIdentityProvider(tokens=tokens),
        )
