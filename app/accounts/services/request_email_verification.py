from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounts.exceptions import ResendLimitReachedError, ResendTooSoonError
from app.accounts.services.email_verification_provider import EmailVerificationProvider
from app.db.models.app_user import AppUser
from app.db.models.email_verification_request import EmailVerificationRequest

RESEND_COOLDOWN: Final = timedelta(seconds=60)
RESEND_WINDOW: Final = timedelta(hours=1)
RESEND_LIMIT_PER_WINDOW: Final = 5


def request_email_verification(
    *,
    email: str,
    session: Session,
    provider: EmailVerificationProvider,
) -> None:
    """Send a verification code to an address that is still unverified.

    Returns normally when the address is unknown or already verified, so this
    operation cannot be used to discover which emails are registered. The rate
    limit is keyed on the account, never on the caller's address, so a shared
    connection cannot lock a legitimate user out.

    Owns the transaction: the provider call happens before the row is written, so
    a delivery failure does not consume one of the caller's attempts.
    """
    normalized_email = email.strip().lower()

    record = (
        session.execute(
            select(AppUser.id, AppUser.email_verified_at).where(
                AppUser.email == normalized_email
            )
        )
        .tuples()
        .one_or_none()
    )

    if record is None:
        return

    user_id, email_verified_at = record
    if email_verified_at is not None:
        return

    now = datetime.now(UTC)
    sent_in_window, last_sent_at = (
        session.execute(
            select(
                func.count(EmailVerificationRequest.id),
                func.max(EmailVerificationRequest.created_at),
            ).where(
                EmailVerificationRequest.user_id == user_id,
                EmailVerificationRequest.created_at >= now - RESEND_WINDOW,
            )
        )
        .tuples()
        .one()
    )

    if last_sent_at is not None and now - last_sent_at < RESEND_COOLDOWN:
        raise ResendTooSoonError
    if sent_in_window >= RESEND_LIMIT_PER_WINDOW:
        raise ResendLimitReachedError

    try:
        provider.send_code(email=normalized_email)
        session.add(EmailVerificationRequest(user_id=user_id))
        session.commit()
    except Exception:
        session.rollback()
        raise
