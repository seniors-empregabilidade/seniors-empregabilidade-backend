from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.accounts.exceptions import InvalidVerificationCodeError
from app.accounts.services.email_verification_provider import EmailVerificationProvider
from app.db.models.app_user import AppUser


def confirm_email_verification(
    *,
    email: str,
    code: str,
    session: Session,
    provider: EmailVerificationProvider,
) -> None:
    """Mark an address as verified once the provider accepts its code.

    An unknown address fails exactly like a wrong code, so the operation cannot
    be used to discover which emails are registered. The provider is only called
    for an address that exists here, so this endpoint cannot be used to probe the
    provider either.

    Confirming twice is harmless: the second call still needs a code the provider
    accepts, and the update refuses to move a timestamp that is already set, so
    the original verification time survives.

    Reads only the two columns it needs, so `password_hash` never enters this
    operation.
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
        raise InvalidVerificationCodeError

    user_id, email_verified_at = record

    provider.confirm_code(email=normalized_email, code=code)

    if email_verified_at is not None:
        return

    try:
        session.execute(
            update(AppUser)
            .where(AppUser.id == user_id, AppUser.email_verified_at.is_(None))
            .values(email_verified_at=datetime.now(UTC))
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
