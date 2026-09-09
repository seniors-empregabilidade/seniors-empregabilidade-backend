import os
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts.exceptions import InvalidVerificationCodeError
from app.accounts.services.confirm_email_verification import (
    confirm_email_verification,
)
from app.db.models.app_user import AppUser
from tests.accounts.conftest import FakeEmailVerificationProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
        reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
    ),
]


def _verified_at(session: Session, email: str) -> datetime | None:
    return session.execute(
        select(AppUser.email_verified_at).where(AppUser.email == email)
    ).scalar_one()


def test_an_accepted_code_marks_the_address_as_verified(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    confirm_email_verification(
        email=unverified_user.email,
        code="123456",
        session=session,
        provider=provider,
    )

    assert provider.confirmed == [(unverified_user.email, "123456")]
    assert _verified_at(session, unverified_user.email) is not None


def test_an_unknown_address_fails_like_a_wrong_code(
    session: Session,
    provider: FakeEmailVerificationProvider,
) -> None:
    with pytest.raises(InvalidVerificationCodeError):
        confirm_email_verification(
            email=f"{uuid4()}@example.invalid",
            code="123456",
            session=session,
            provider=provider,
        )

    assert provider.confirmed == []


def test_a_rejected_code_leaves_the_address_unverified(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    provider.failure = InvalidVerificationCodeError()

    with pytest.raises(InvalidVerificationCodeError):
        confirm_email_verification(
            email=unverified_user.email,
            code="000000",
            session=session,
            provider=provider,
        )

    assert _verified_at(session, unverified_user.email) is None


def test_confirming_twice_keeps_the_original_verification_time(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    confirm_email_verification(
        email=unverified_user.email,
        code="123456",
        session=session,
        provider=provider,
    )
    first_time = _verified_at(session, unverified_user.email)

    confirm_email_verification(
        email=unverified_user.email,
        code="123456",
        session=session,
        provider=provider,
    )

    assert _verified_at(session, unverified_user.email) == first_time


def test_the_address_is_matched_regardless_of_letter_case(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    confirm_email_verification(
        email=unverified_user.email.upper(),
        code="123456",
        session=session,
        provider=provider,
    )

    assert _verified_at(session, unverified_user.email) is not None
