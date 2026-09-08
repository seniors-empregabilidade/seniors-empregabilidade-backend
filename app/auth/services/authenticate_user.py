import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.exceptions import AccountNotActiveError
from app.auth.services.identity_provider import IdentityProvider, IdentityTokens
from app.core.middleware import get_request_id
from app.db.models.app_user import AppUser
from app.db.models.enums import AccountStatus, UserType

_auth_logger = logging.getLogger("app.auth")


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """The result of a successful sign-in, ready to map onto the response DTO."""

    tokens: IdentityTokens
    user_id: UUID
    user_type: UserType


def authenticate_user(
    *,
    email: str,
    password: str,
    session: Session,
    identity_provider: IdentityProvider,
) -> AuthenticatedUser:
    """Verify credentials with the identity provider and open a session.

    The provider owns the password, so it decides first. Only a caller that
    already proved the password reaches the local account checks, which is why
    those may answer with a distinct status without enabling user enumeration.

    Reads no columns beyond the three it needs, so `password_hash` never enters
    this process on the sign-in path.
    """
    tokens = identity_provider.authenticate(email=email, password=password)

    record = (
        session.execute(
            select(AppUser.id, AppUser.user_type, AppUser.account_status).where(
                AppUser.email == email
            )
        )
        .tuples()
        .one_or_none()
    )

    if record is None:
        # Authenticated by the provider but absent here: a provisioning gap.
        # Answered like a blocked account so a valid credential cannot be used
        # to probe which emails exist in this database.
        _auth_logger.warning(
            "login_user_not_provisioned",
            extra={
                "event": "login_user_not_provisioned",
                "request_id": get_request_id(),
            },
        )
        raise AccountNotActiveError

    user_id, user_type, account_status = record
    if account_status is not AccountStatus.ACTIVE:
        raise AccountNotActiveError

    return AuthenticatedUser(tokens=tokens, user_id=user_id, user_type=user_type)
