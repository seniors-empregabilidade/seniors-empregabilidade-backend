from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import require_administrator, require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.candidates.domain.certificate_document import MAX_DOCUMENT_BYTES
from app.candidates.schemas import (
    CertificationCreateRequest,
    CertificationDocumentLinkResponse,
    CertificationDocumentResponse,
    CertificationResponse,
    CertificationUpdateRequest,
    EducationCreateRequest,
    EducationResponse,
    EducationUpdateRequest,
    ExperienceCreateRequest,
    ExperienceResponse,
    ExperienceUpdateRequest,
    GuidanceCreateRequest,
    GuidanceResponse,
    ProfessionalProfileResponse,
    ProfessionalProfileUpdateRequest,
    ProfessionalRegistrationRequest,
    ProfessionalRegistrationResponse,
    ProfessionalSummaryResponse,
    SkillLinkRequest,
    SkillSelectionRequest,
)
from app.candidates.services import (
    add_certification,
    add_education,
    add_experience,
    add_skill,
    attach_document,
    document_link,
    get_profile,
    list_professionals,
    record_guidance,
    register_professional,
    remove_certification,
    remove_document,
    remove_education,
    remove_experience,
    remove_skill,
    replace_skills,
    update_certification,
    update_education,
    update_experience,
    update_profile,
)
from app.candidates.services.certification_documents import DocumentLink
from app.candidates.services.guidance_record import GuidanceRecord
from app.candidates.services.professional_summary import ProfessionalSummary
from app.candidates.services.records import (
    CertificationRecord,
    EducationRecord,
    ExperienceRecord,
    ProfileRecord,
)
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.provider import IdentityProvider
from app.skills.schemas import SkillResponse
from app.skills.services import CatalogSkill
from app.storage.dependencies import get_document_storage
from app.storage.document_storage import DocumentStorage

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


@router.get("", response_model=list[ProfessionalSummaryResponse])
def read_professionals(
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
    completeness: Annotated[Literal["complete", "incomplete"] | None, Query()] = None,
    contact_status: Annotated[
        Literal["contacted", "not_contacted"] | None, Query()
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProfessionalSummaryResponse]:
    response.headers["Cache-Control"] = "no-store"
    summaries = list_professionals(
        session=session,
        completeness=completeness,
        contact_status=contact_status,
        limit=limit,
        offset=offset,
    )
    return [_professional_summary_response(item) for item in summaries]


@router.post(
    "/{professional_id}/guidance", response_model=GuidanceResponse, status_code=201
)
def create_guidance(
    professional_id: UUID,
    request: GuidanceCreateRequest,
    administrator: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> GuidanceResponse:
    response.headers["Cache-Control"] = "no-store"
    return _guidance_response(
        record_guidance(
            professional_id,
            administrator.id,
            request.note,
            session=session,
        )
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


@router.post("/me/skills", response_model=SkillResponse, status_code=201)
def create_skill_link(
    request: SkillLinkRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> SkillResponse:
    response.headers["Cache-Control"] = "no-store"
    return _skill_response(add_skill(current_user.id, request, session=session))


@router.put("/me/skills", response_model=list[SkillResponse])
def replace_skill_links(
    request: SkillSelectionRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> list[SkillResponse]:
    response.headers["Cache-Control"] = "no-store"
    skills = replace_skills(current_user.id, request, session=session)
    return [_skill_response(skill) for skill in skills]


@router.delete("/me/skills/{skill_id}", status_code=204, response_class=Response)
def delete_skill_link(
    skill_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    remove_skill(current_user.id, skill_id, session=session)


@router.post(
    "/me/certifications", response_model=CertificationResponse, status_code=201
)
def create_certification(
    request: CertificationCreateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> CertificationResponse:
    response.headers["Cache-Control"] = "no-store"
    record = add_certification(current_user.id, request, session=session)
    return _certification_response(record)


@router.patch(
    "/me/certifications/{certification_id}", response_model=CertificationResponse
)
def edit_certification(
    certification_id: UUID,
    request: CertificationUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    response: Response,
) -> CertificationResponse:
    response.headers["Cache-Control"] = "no-store"
    record = update_certification(
        current_user.id, certification_id, request, session=session
    )
    return _certification_response(record)


@router.delete(
    "/me/certifications/{certification_id}",
    status_code=204,
    response_class=Response,
)
def delete_certification(
    certification_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
) -> None:
    remove_certification(
        current_user.id, certification_id, session=session, storage=storage
    )


@router.put(
    "/me/certifications/{certification_id}/document",
    response_model=CertificationResponse,
)
def upload_certification_document(
    certification_id: UUID,
    file: UploadFile,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
    response: Response,
) -> CertificationResponse:
    response.headers["Cache-Control"] = "no-store"
    # Reading one byte past the limit is enough to reject an oversized file.
    content = file.file.read(MAX_DOCUMENT_BYTES + 1)
    record = attach_document(
        current_user.id,
        certification_id,
        file.filename,
        content,
        session=session,
        storage=storage,
    )
    return _certification_response(record)


@router.delete(
    "/me/certifications/{certification_id}/document",
    status_code=204,
    response_class=Response,
)
def delete_certification_document(
    certification_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
) -> None:
    remove_document(current_user.id, certification_id, session=session, storage=storage)


@router.get(
    "/me/certifications/{certification_id}/document",
    response_model=CertificationDocumentLinkResponse,
)
def read_own_certification_document(
    certification_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_candidate)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
    response: Response,
) -> CertificationDocumentLinkResponse:
    response.headers["Cache-Control"] = "no-store"
    link = document_link(
        current_user.id, certification_id, session=session, storage=storage
    )
    return _document_link_response(link)


@router.get(
    "/{professional_id}/certifications/{certification_id}/document",
    response_model=CertificationDocumentLinkResponse,
)
def read_professional_certification_document(
    professional_id: UUID,
    certification_id: UUID,
    _: Annotated[CurrentUser, Depends(require_administrator)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[DocumentStorage, Depends(get_document_storage)],
    response: Response,
) -> CertificationDocumentLinkResponse:
    response.headers["Cache-Control"] = "no-store"
    link = document_link(
        professional_id, certification_id, session=session, storage=storage
    )
    return _document_link_response(link)


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
        certifications=[
            _certification_response(item) for item in record.certifications
        ],
        skills=[_skill_response(item) for item in record.skills],
        missing_fields=list(record.missing_fields),
    )


def _professional_summary_response(
    record: ProfessionalSummary,
) -> ProfessionalSummaryResponse:
    return ProfessionalSummaryResponse(
        id=record.id,
        full_name=record.full_name,
        email=record.email,
        phone=record.phone,
        city=record.city,
        state=record.state,
        missing_fields=list(record.missing_fields),
        last_guidance=_guidance_response(record.last_guidance)
        if record.last_guidance
        else None,
    )


def _guidance_response(record: GuidanceRecord) -> GuidanceResponse:
    return GuidanceResponse(
        id=record.id,
        note=record.note,
        created_at=record.created_at,
        administrator_name=record.administrator_name,
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


def _skill_response(record: CatalogSkill) -> SkillResponse:
    return SkillResponse(id=record.id, name=record.name, type=record.type)


def _certification_response(record: CertificationRecord) -> CertificationResponse:
    document = record.document
    return CertificationResponse(
        id=record.id,
        name=record.name,
        issuer=record.issuer,
        issued_date=record.issued_date,
        expiration_date=record.expiration_date,
        document=CertificationDocumentResponse(
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            uploaded_at=document.uploaded_at,
        )
        if document is not None
        else None,
    )


def _document_link_response(link: DocumentLink) -> CertificationDocumentLinkResponse:
    return CertificationDocumentLinkResponse(url=link.url, expires_at=link.expires_at)
