from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.candidates.schemas import (
    EducationCreateRequest,
    EducationResponse,
    EducationUpdateRequest,
    ExperienceCreateRequest,
    ExperienceResponse,
    ExperienceUpdateRequest,
    ProfessionalProfileResponse,
    ProfessionalProfileUpdateRequest,
    ProfessionalRegistrationRequest,
    ProfessionalRegistrationResponse,
)
from app.candidates.services import (
    add_education,
    add_experience,
    get_profile,
    register_professional,
    remove_education,
    remove_experience,
    update_education,
    update_experience,
    update_profile,
)
from app.candidates.services.records import (
    EducationRecord,
    ExperienceRecord,
    ProfileRecord,
)
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
    return _profile_response(get_profile(current_user.id, session=session))


@router.patch("/me", response_model=ProfessionalProfileResponse)
def edit_profile(
    request: ProfessionalProfileUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> ProfessionalProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    return _profile_response(update_profile(current_user.id, request, session=session))


@router.post("/me/experiences", response_model=ExperienceResponse, status_code=201)
def create_experience(
    request: ExperienceCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> ExperienceResponse:
    response.headers["Cache-Control"] = "no-store"
    record = add_experience(current_user.id, request, session=session)
    return _experience_response(record)


@router.patch("/me/experiences/{experience_id}", response_model=ExperienceResponse)
def edit_experience(
    experience_id: UUID,
    request: ExperienceUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> ExperienceResponse:
    response.headers["Cache-Control"] = "no-store"
    record = update_experience(current_user.id, experience_id, request, session=session)
    return _experience_response(record)


@router.delete(
    "/me/experiences/{experience_id}", status_code=204, response_class=Response
)
def delete_experience(
    experience_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    remove_experience(current_user.id, experience_id, session=session)


@router.post("/me/education", response_model=EducationResponse, status_code=201)
def create_education(
    request: EducationCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> EducationResponse:
    response.headers["Cache-Control"] = "no-store"
    record = add_education(current_user.id, request, session=session)
    return _education_response(record)


@router.patch("/me/education/{education_id}", response_model=EducationResponse)
def edit_education(
    education_id: UUID,
    request: EducationUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> EducationResponse:
    response.headers["Cache-Control"] = "no-store"
    record = update_education(current_user.id, education_id, request, session=session)
    return _education_response(record)


@router.delete("/me/education/{education_id}", status_code=204, response_class=Response)
def delete_education(
    education_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    remove_education(current_user.id, education_id, session=session)


def _profile_response(record: ProfileRecord) -> ProfessionalProfileResponse:
    return ProfessionalProfileResponse(
        id=record.id,
        full_name=record.full_name,
        age=record.age,
        email=record.email,
        phone=record.phone,
        city=record.city,
        state=record.state,
        summary=record.summary,
        experiences=[_experience_response(item) for item in record.experiences],
        education=[_education_response(item) for item in record.education],
        skills=list(record.skills),
    )


def _experience_response(record: ExperienceRecord) -> ExperienceResponse:
    return ExperienceResponse(
        id=record.id,
        role=record.role,
        company_name=record.company_name,
        start_date=record.start_date,
        end_date=record.end_date,
        description=record.description,
    )


def _education_response(record: EducationRecord) -> EducationResponse:
    return EducationResponse(
        id=record.id,
        institution=record.institution,
        degree=record.degree,
        field=record.field,
        start_date=record.start_date,
        end_date=record.end_date,
    )
