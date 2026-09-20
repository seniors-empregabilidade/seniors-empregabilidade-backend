from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.accounts.schemas.email_confirmation import (
    EmailConfirmationRequest,
    EmailRequest,
)
from app.core.problem_details import PROBLEM_RESPONSE
from app.core.rate_limit import SENSITIVE_LIMIT, limiter
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider

router = APIRouter(
    prefix="/email-verification",
    tags=["accounts"],
    responses={code: PROBLEM_RESPONSE for code in (422, 429, 503)},
)


@router.post("/confirm", status_code=204)
def confirm_email(
    request: EmailConfirmationRequest,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> Response:
    provider.confirm_email(email=request.email, code=request.code.get_secret_value())
    return Response(status_code=204)


# Dispara e-mail pelo Cognito, cujo remetente padrão tem teto de 50 por dia.
# Sem limite, cinquenta requisições quebram o cadastro do dia inteiro.
@router.post("/send", status_code=202)
@limiter.limit(SENSITIVE_LIMIT)
def resend_confirmation(
    request: Request,
    payload: EmailRequest,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> Response:
    provider.resend_confirmation(email=payload.email)
    return Response(status_code=202)
