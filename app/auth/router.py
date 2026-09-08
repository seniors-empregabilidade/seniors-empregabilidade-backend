from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.integrations.cognito import CognitoIdentityProvider
from app.auth.schemas.login_request import LoginRequest
from app.auth.schemas.login_response import LoginResponse
from app.auth.services.authenticate_user import authenticate_user
from app.auth.services.identity_provider import IdentityProvider
from app.core.config import Settings, get_settings
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


def provide_identity_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> IdentityProvider:
    return CognitoIdentityProvider(settings)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=200,
    summary="Sign in with email and password",
    responses={
        401: {"description": "The email or password is incorrect"},
        403: {"description": "The account cannot sign in"},
        422: {"description": "The request contains invalid data"},
        429: {"description": "Too many sign-in attempts"},
        502: {"description": "The identity provider is unavailable"},
    },
)
def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    identity_provider: Annotated[IdentityProvider, Depends(provide_identity_provider)],
) -> LoginResponse:
    # RFC 6749 section 5.1: token responses must not be stored by caches.
    response.headers["Cache-Control"] = "no-store"
    result = authenticate_user(
        email=payload.email,
        password=payload.password.get_secret_value(),
        session=session,
        identity_provider=identity_provider,
    )
    return LoginResponse(
        access_token=result.tokens.access_token,
        id_token=result.tokens.id_token,
        refresh_token=result.tokens.refresh_token,
        expires_in=result.tokens.expires_in,
        token_type=result.tokens.token_type,
        user_id=result.user_id,
        user_type=result.user_type,
    )
