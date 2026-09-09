from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.accounts.integrations.cognito_email_verification import (
    CognitoEmailVerificationProvider,
)
from app.accounts.schemas.confirm_verification_code_request import (
    ConfirmVerificationCodeRequest,
)
from app.accounts.schemas.send_verification_code_request import (
    SendVerificationCodeRequest,
)
from app.accounts.services.confirm_email_verification import confirm_email_verification
from app.accounts.services.email_verification_provider import EmailVerificationProvider
from app.accounts.services.request_email_verification import request_email_verification
from app.core.config import Settings, get_settings
from app.db.session import get_session

router = APIRouter(prefix="/email-verification", tags=["email verification"])


def provide_email_verification_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailVerificationProvider:
    return CognitoEmailVerificationProvider(settings)


@router.post(
    "/send",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    summary="Send a verification code to an email address",
    responses={
        202: {"description": "The request was accepted"},
        422: {"description": "The request contains invalid data"},
        429: {"description": "A code was sent recently, or too many were requested"},
        502: {"description": "The verification service is unavailable"},
    },
)
def send_verification_code(
    payload: SendVerificationCodeRequest,
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[
        EmailVerificationProvider, Depends(provide_email_verification_provider)
    ],
) -> Response:
    """Send a verification code, whether or not one was sent before.

    Answers 202 for any address that is not rate limited, including one that is
    unknown or already verified, so the response cannot be used to discover which
    emails are registered.
    """
    request_email_verification(email=payload.email, session=session, provider=provider)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Confirm an email address with its verification code",
    responses={
        204: {"description": "The address is verified"},
        422: {"description": "The code is invalid or expired"},
        429: {"description": "Too many verification attempts"},
        502: {"description": "The verification service is unavailable"},
    },
)
def confirm_verification_code(
    payload: ConfirmVerificationCodeRequest,
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[
        EmailVerificationProvider, Depends(provide_email_verification_provider)
    ],
) -> Response:
    """Mark the address as verified when the provider accepts the code."""
    confirm_email_verification(
        email=payload.email,
        code=payload.code,
        session=session,
        provider=provider,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
