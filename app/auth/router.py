from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas.current_user import CurrentUser
from app.auth.schemas.login_request import LoginRequest
from app.auth.schemas.login_response import LoginResponse
from app.auth.services.login import authenticate_user
from app.core.problem_details import PROBLEM_RESPONSE
from app.core.rate_limit import SENSITIVE_LIMIT, limiter
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 409, 422, 429, 503)},
)


# Limitado por origem: sem isso, a rota de login é o alvo natural de força
# bruta, e o WAF que faria esse trabalho é negado pela SCP da conta.
@router.post("/login", response_model=LoginResponse)
@limiter.limit(SENSITIVE_LIMIT)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
    session: Annotated[Session, Depends(get_session)],
) -> LoginResponse:
    result = authenticate_user(payload, provider=provider, session=session)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/me", response_model=CurrentUser)
def me(
    user: Annotated[CurrentUser, Depends(get_current_user)], response: Response
) -> CurrentUser:
    response.headers["Cache-Control"] = "no-store"
    return user
