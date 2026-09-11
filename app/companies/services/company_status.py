from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.companies.schemas.company_status import CompanyStatusResponse
from app.core.errors import ProblemException
from app.db.models import Company, Notification
from app.db.models.enums import CompanyStatus


def get_company_status(session: Session, user_id: UUID) -> CompanyStatusResponse:
    company = session.get(Company, user_id)
    if company is None:
        raise ProblemException(
            status_code=403,
            title="Forbidden",
            code="company_account_required",
            detail="A company account is required.",
        )
    reason = None
    if company.status == CompanyStatus.REJECTED:
        reason = session.scalar(
            select(Notification.message)
            .where(
                Notification.user_id == user_id,
                Notification.type == "company_registration_rejected",
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(1)
        )
    return CompanyStatusResponse(
        id=company.id, status=company.status, rejection_reason=reason
    )
