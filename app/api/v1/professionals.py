from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.professional import (
    ProfessionalCreateRequest,
    ProfessionalCreateResponse,
)
from app.use_cases.register_professional import register_candidate

router = APIRouter()


@router.post(
    "/professionals",
    response_model=ProfessionalCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new professional",
)
def create_professional(
    request: ProfessionalCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ProfessionalCreateResponse:
    """Endpoint to register a professional.

    Returns the newly created professional ID and a confirmation message.
    Validation errors raise ``ProblemException`` which is handled globally.
    """
    candidate_id = register_candidate(request, session)
    return ProfessionalCreateResponse(id=candidate_id)
