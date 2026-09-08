from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import pytest

from app.auth.services.identity_provider import IdentityProvider, IdentityTokens
from app.db.models.enums import AccountStatus, UserType

DEMO_USER_ID = UUID("11111111-1111-5111-8111-111111111111")

# The three columns the sign-in query reads, in the order it selects them.
UserRecord = tuple[UUID, UserType, AccountStatus]


@dataclass
class FakeIdentityProvider:
    """Controlled stand-in for Cognito that records what it was asked."""

    tokens: IdentityTokens | None = None
    error: Exception | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)

    def authenticate(self, *, email: str, password: str) -> IdentityTokens:
        self.calls.append((email, password))
        if self.error is not None:
            raise self.error
        if self.tokens is None:
            raise AssertionError("FakeIdentityProvider needs tokens or an error")
        return self.tokens


def assert_implements_port(provider: FakeIdentityProvider) -> IdentityProvider:
    """Fail type checking if the fake and the real port ever drift apart."""
    return provider


@dataclass
class FakeResult:
    record: UserRecord | None

    def tuples(self) -> FakeResult:
        return self

    def one_or_none(self) -> UserRecord | None:
        return self.record


@dataclass
class FakeSession:
    """Returns one canned record for the single query the operation issues."""

    record: UserRecord | None = None
    executed: int = 0

    def execute(self, *args: Any, **kwargs: Any) -> FakeResult:
        self.executed += 1
        return FakeResult(self.record)


@pytest.fixture
def tokens() -> IdentityTokens:
    return IdentityTokens(
        access_token="access-token-value",
        id_token="id-token-value",
        refresh_token="refresh-token-value",
        expires_in=3600,
        token_type="Bearer",
    )


@pytest.fixture
def active_record() -> UserRecord:
    return (DEMO_USER_ID, UserType.CANDIDATE, AccountStatus.ACTIVE)
