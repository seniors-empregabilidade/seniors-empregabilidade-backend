from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.candidates.schemas import (
    ProfessionalRegistrationRequest,
    ProfessionalRegistrationResponse,
)
from app.candidates.services import register_professional
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider

router = APIRouter(
    prefix="/professionals",
    tags=["candidates"],
    responses={code: PROBLEM_RESPONSE for code in (409, 422, 429, 503)},
)


@router.post("", response_model=ProfessionalRegistrationResponse, status_code=201)
def create_professional(
    request: ProfessionalRegistrationRequest,
    session: Annotated[Session, Depends(get_session)],
    identity_provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> ProfessionalRegistrationResponse:
    registered = register_professional(
        request,
        session=session,
        identity_provider=identity_provider,
    )
    return ProfessionalRegistrationResponse(
        id=registered.id,
        full_name=registered.full_name,
        email=registered.email,
        email_verification_required=registered.email_verification_required,
    )
