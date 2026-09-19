from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.candidates.schemas import (
    ProfessionalProfileResponse,
    ProfessionalProfileUpdateRequest,
    ProfessionalRegistrationRequest,
    ProfessionalRegistrationResponse,
)
from app.candidates.services import get_profile, register_professional, update_profile
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider

router = APIRouter(
    prefix="/professionals",
    tags=["candidates"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 404, 409, 422, 429, 503)},
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


@router.get("/me", response_model=ProfessionalProfileResponse)
def read_profile(
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> ProfessionalProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    return get_profile(current_user.id, session=session)


@router.patch("/me", response_model=ProfessionalProfileResponse)
def edit_profile(
    request: ProfessionalProfileUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> ProfessionalProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    return update_profile(current_user.id, request, session=session)
