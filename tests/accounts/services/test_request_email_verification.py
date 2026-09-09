import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounts.exceptions import ResendLimitReachedError, ResendTooSoonError
from app.accounts.services.request_email_verification import (
    RESEND_LIMIT_PER_WINDOW,
    request_email_verification,
)
from app.db.models.app_user import AppUser
from app.db.models.email_verification_request import EmailVerificationRequest
from tests.accounts.conftest import FakeEmailVerificationProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
        reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
    ),
]


def _requests_for(session: Session, user_id: UUID) -> int:
    return session.execute(
        select(func.count(EmailVerificationRequest.id)).where(
            EmailVerificationRequest.user_id == user_id
        )
    ).scalar_one()


def _record_sends(
    session: Session, user_id: UUID, *, count: int, minutes_ago: int
) -> None:
    sent_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    for _ in range(count):
        session.add(EmailVerificationRequest(user_id=user_id, created_at=sent_at))
    session.flush()


def test_sends_a_code_and_records_the_request(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    request_email_verification(
        email=unverified_user.email, session=session, provider=provider
    )

    assert provider.sent_to == [unverified_user.email]
    assert _requests_for(session, unverified_user.id) == 1


def test_an_unknown_address_is_accepted_without_sending(
    session: Session,
    provider: FakeEmailVerificationProvider,
) -> None:
    request_email_verification(
        email=f"{uuid4()}@example.invalid", session=session, provider=provider
    )

    assert provider.sent_to == []


def test_an_already_verified_address_is_accepted_without_sending(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    unverified_user.email_verified_at = datetime.now(UTC)
    session.flush()

    request_email_verification(
        email=unverified_user.email, session=session, provider=provider
    )

    assert provider.sent_to == []
    assert _requests_for(session, unverified_user.id) == 0


def test_a_second_request_inside_the_cooldown_is_refused(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    request_email_verification(
        email=unverified_user.email, session=session, provider=provider
    )

    with pytest.raises(ResendTooSoonError):
        request_email_verification(
            email=unverified_user.email, session=session, provider=provider
        )

    assert _requests_for(session, unverified_user.id) == 1


def test_a_request_beyond_the_hourly_allowance_is_refused(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    _record_sends(
        session, unverified_user.id, count=RESEND_LIMIT_PER_WINDOW, minutes_ago=30
    )

    with pytest.raises(ResendLimitReachedError):
        request_email_verification(
            email=unverified_user.email, session=session, provider=provider
        )

    assert provider.sent_to == []


def test_sends_beyond_the_window_do_not_count_against_the_allowance(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    _record_sends(
        session, unverified_user.id, count=RESEND_LIMIT_PER_WINDOW, minutes_ago=90
    )

    request_email_verification(
        email=unverified_user.email, session=session, provider=provider
    )

    assert provider.sent_to == [unverified_user.email]


def test_a_delivery_failure_does_not_consume_an_attempt(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    provider.failure = RuntimeError("provider is down")

    with pytest.raises(RuntimeError):
        request_email_verification(
            email=unverified_user.email, session=session, provider=provider
        )

    assert _requests_for(session, unverified_user.id) == 0


def test_the_allowance_is_counted_per_account(
    session: Session,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    other = AppUser(
        email=f"{uuid4()}@example.invalid",
        password_hash="not-a-real-hash",
        user_type="candidate",
    )
    session.add(other)
    session.flush()
    _record_sends(session, other.id, count=RESEND_LIMIT_PER_WINDOW, minutes_ago=30)

    request_email_verification(
        email=unverified_user.email, session=session, provider=provider
    )

    assert provider.sent_to == [unverified_user.email]
