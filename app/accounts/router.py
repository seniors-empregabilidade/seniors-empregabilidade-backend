from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.accounts.schemas.email_confirmation import (
    EmailConfirmationRequest,
    EmailRequest,
)
from app.accounts.services.confirm_email import confirm_account_email
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider

router = APIRouter(
    prefix="/email-verification",
    tags=["accounts"],
    responses={code: PROBLEM_RESPONSE for code in (401, 422, 429, 503)},
)


@router.post("/confirm", status_code=204)
def confirm_email(
    request: EmailConfirmationRequest,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    confirm_account_email(request, provider=provider, session=session)
    return Response(status_code=204)


@router.post("/send", status_code=202)
def resend_confirmation(
    request: EmailRequest,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> Response:
    provider.resend_confirmation(email=request.email)
    return Response(status_code=202)
