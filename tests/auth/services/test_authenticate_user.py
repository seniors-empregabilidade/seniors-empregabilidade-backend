from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.auth.exceptions import AccountNotActiveError, InvalidCredentialsError
from app.auth.services.authenticate_user import authenticate_user
from app.auth.services.identity_provider import IdentityTokens
from app.db.models.enums import AccountStatus, UserType
from tests.auth.conftest import (
    DEMO_USER_ID,
    FakeIdentityProvider,
    FakeSession,
    UserRecord,
)


def run(
    provider: FakeIdentityProvider,
    session: FakeSession,
    email: str = "candidate@example.invalid",
) -> object:
    return authenticate_user(
        email=email,
        password="LocalDemoOnly!2026",
        session=cast(Session, session),
        identity_provider=provider,
    )


def test_successful_sign_in_returns_the_tokens_and_the_role(
    tokens: IdentityTokens, active_record: UserRecord
) -> None:
    provider = FakeIdentityProvider(tokens=tokens)

    result = authenticate_user(
        email="candidate@example.invalid",
        password="LocalDemoOnly!2026",
        session=cast(Session, FakeSession(record=active_record)),
        identity_provider=provider,
    )

    assert result.tokens is tokens
    assert result.user_id == DEMO_USER_ID
    assert result.user_type is UserType.CANDIDATE


def test_the_provider_decides_before_the_database_is_read() -> None:
    session = FakeSession(record=None)
    provider = FakeIdentityProvider(error=InvalidCredentialsError())

    with pytest.raises(InvalidCredentialsError):
        run(provider, session)

    assert session.executed == 0


def test_an_identity_without_a_local_record_cannot_sign_in(
    tokens: IdentityTokens,
) -> None:
    provider = FakeIdentityProvider(tokens=tokens)

    with pytest.raises(AccountNotActiveError):
        run(provider, FakeSession(record=None))


@pytest.mark.parametrize("status", [AccountStatus.SUSPENDED, AccountStatus.BLOCKED])
def test_a_non_active_account_cannot_sign_in(
    tokens: IdentityTokens, status: AccountStatus
) -> None:
    record = (DEMO_USER_ID, UserType.COMPANY, status)
    provider = FakeIdentityProvider(tokens=tokens)

    with pytest.raises(AccountNotActiveError) as failure:
        run(provider, FakeSession(record=record))

    assert failure.value.status_code == 403
    assert failure.value.code == "account_not_active"


def test_the_same_failure_hides_whether_the_account_exists(
    tokens: IdentityTokens,
) -> None:
    provider = FakeIdentityProvider(tokens=tokens)
    missing = FakeSession(record=None)
    blocked = FakeSession(
        record=(DEMO_USER_ID, UserType.CANDIDATE, AccountStatus.BLOCKED)
    )

    with pytest.raises(AccountNotActiveError) as absent_failure:
        run(provider, missing)
    with pytest.raises(AccountNotActiveError) as blocked_failure:
        run(provider, blocked)

    assert absent_failure.value.code == blocked_failure.value.code
    assert absent_failure.value.detail == blocked_failure.value.detail
