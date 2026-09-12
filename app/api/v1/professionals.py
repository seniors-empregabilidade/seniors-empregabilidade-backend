from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.schemas.professional import ProfessionalCreateRequest, ProfessionalCreateResponse
from app.use_cases.register_professional import register_professional
from app.db.session import get_session

router = APIRouter()

@router.post(
    "/professionals",
    response_model=ProfessionalCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new professional",
)
def create_professional(
    request: ProfessionalCreateRequest,
    session: Session = Depends(get_session),
):
    """Endpoint to register a professional.

    Returns the newly created professional ID and a confirmation message.
    Validation errors raise ``ProblemException`` which is handled globally.
    """
    professional_id = register_professional(request, session)
    return ProfessionalCreateResponse(id=professional_id)
