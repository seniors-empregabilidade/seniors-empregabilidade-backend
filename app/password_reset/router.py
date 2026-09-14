from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.problem_details import PROBLEM_RESPONSE
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider
from app.password_reset.schemas import PasswordResetRequest

router = APIRouter(
    prefix="/password-reset",
    tags=["password-reset"],
    responses={code: PROBLEM_RESPONSE for code in (422, 429, 503)},
)


@router.post("/send", status_code=202)
def send_password_reset(
    request: PasswordResetRequest,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> Response:
    provider.start_password_reset(email=request.email)
    return Response(status_code=202)
