from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.problem_details import PROBLEM_RESPONSE
from app.support.schemas import SupportContactResponse

router = APIRouter(
    prefix="/support",
    tags=["support"],
    responses={404: PROBLEM_RESPONSE},
)


@router.get("/contact", response_model=SupportContactResponse)
def read_support_contact(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupportContactResponse:
    """Public, so the support button also works before login."""
    if settings.support_whatsapp_number is None:
        raise ProblemException(
            status_code=404,
            title="Not Found",
            code="support_contact_not_configured",
            detail="The support contact is not configured.",
        )
    return SupportContactResponse(
        whatsapp_number=settings.support_whatsapp_number,
        initial_message=settings.support_whatsapp_message,
    )
