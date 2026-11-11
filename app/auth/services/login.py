from sqlalchemy.orm import Session

from app.auth.schemas.login_request import LoginRequest
from app.auth.schemas.login_response import LoginResponse
from app.auth.schemas.refresh_request import RefreshRequest
from app.auth.services.current_user import find_current_user
from app.identity.authenticated_identity import AuthenticatedIdentity
from app.identity.exceptions import InvalidAccessTokenError, InvalidCredentialsError
from app.identity.provider import IdentityProvider


def authenticate_user(
    request: LoginRequest, *, provider: IdentityProvider, session: Session
) -> LoginResponse:
    identity = provider.authenticate(
        email=request.email, password=request.password.get_secret_value()
    )
    return _login_response(identity, session)


def refresh_session(
    request: RefreshRequest, *, provider: IdentityProvider, session: Session
) -> LoginResponse:
    identity = provider.refresh(
        refresh_token=request.refresh_token.get_secret_value(),
        expired_access_token=request.access_token.get_secret_value(),
    )
    return _login_response(identity, session)


def _login_response(identity: AuthenticatedIdentity, session: Session) -> LoginResponse:
    try:
        user = find_current_user(session, identity.identity_subject)
    except InvalidAccessTokenError as exc:
        raise InvalidCredentialsError from exc
    return LoginResponse(
        access_token=identity.tokens.access_token,
        id_token=identity.tokens.id_token,
        refresh_token=identity.tokens.refresh_token,
        expires_in=identity.tokens.expires_in,
        token_type=identity.tokens.token_type,
        user_id=user.id,
        user_type=user.user_type,
    )
