from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_approved_company
from app.auth.schemas.current_user import CurrentUser
from app.contacts.schemas import ContactResponse, CreateContactRequest
from app.contacts.services.contact_professional import contact_professional
from app.core.problem_details import PROBLEM_RESPONSE
from app.db.session import get_session

router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
    responses={code: PROBLEM_RESPONSE for code in (401, 403, 422)},
)


@router.post(
    "",
    response_model=ContactResponse,
    status_code=201,
    responses={code: PROBLEM_RESPONSE for code in (404, 409)},
)
def create_contact(
    request: CreateContactRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_approved_company)],
    session: Annotated[Session, Depends(get_session)],
) -> ContactResponse:
    """Send a message to a professional listed for one of the company's jobs.

    The professional is notified in the platform and by e-mail at the address on
    their account, which the company never receives. `email_status` starts as
    `pending`: the e-mail is sent after this request, and a failure never undoes
    the notification or the contact record.
    """
    response.headers["Cache-Control"] = "no-store"
    sent = contact_professional(
        session,
        company_id=user.id,
        sent_by_user_id=user.id,
        job_id=request.job_id,
        candidate_id=request.candidate_id,
        message=request.message,
    )
    return ContactResponse(
        id=sent.id,
        job_id=sent.job_id,
        candidate_id=sent.candidate_id,
        created_at=sent.created_at,
        email_status=sent.email_status,
    )
