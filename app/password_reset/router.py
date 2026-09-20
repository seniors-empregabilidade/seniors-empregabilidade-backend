from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.problem_details import PROBLEM_RESPONSE
from app.core.rate_limit import SENSITIVE_LIMIT, limiter
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider
from app.password_reset.schemas import (
    PasswordResetConfirmationRequest,
    PasswordResetRequest,
)

router = APIRouter(
    prefix="/password-reset",
    tags=["password-reset"],
    responses={code: PROBLEM_RESPONSE for code in (422, 429, 503)},
)


# Mesma razão do reenvio de confirmação: dispara e-mail e a cota é diária.
@router.post("/send", status_code=202)
@limiter.limit(SENSITIVE_LIMIT)
def send_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> Response:
    provider.start_password_reset(email=payload.email)
    return Response(status_code=202)


@router.post("/confirm", status_code=204)
def confirm_password_reset(
    request: PasswordResetConfirmationRequest,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> Response:
    provider.confirm_password_reset(
        email=request.email,
        code=request.code.get_secret_value(),
        password=request.password.get_secret_value(),
    )
    return Response(status_code=204)
