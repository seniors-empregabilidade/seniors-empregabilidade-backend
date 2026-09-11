from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.companies.domain.policies.cnae_policy import ensure_cnae_is_allowed
from app.companies.schemas.company_approval import CompanyApprovalRequest
from app.companies.schemas.company_response import CompanyResponse
from app.core.errors import ProblemException
from app.db.models import AppUser, Company, Notification
from app.db.models.enums import CompanyStatus


def review_company(
    company_id: UUID,
    request: CompanyApprovalRequest,
    *,
    session: Session,
    blocked_cnae_prefixes: tuple[str, ...],
) -> CompanyResponse:
    try:
        company = session.scalar(
            select(Company).where(Company.id == company_id).with_for_update()
        )
        if company is None:
            raise ProblemException(
                status_code=404,
                title="Not Found",
                code="company_not_found",
                detail="The company was not found.",
            )
        if company.status != CompanyStatus.PENDING:
            raise ProblemException(
                status_code=409,
                title="Conflict",
                code="company_not_pending",
                detail="Only pending companies can be approved or rejected.",
            )
        if request.status == "approved":
            if not company.primary_cnae:
                raise ProblemException(
                    status_code=422,
                    title="Validation Error",
                    code="company_activity_required",
                    detail="The company must have a verified economic activity.",
                )
            ensure_cnae_is_allowed(company.primary_cnae, blocked_cnae_prefixes)
        company.status = CompanyStatus(request.status)
        if request.status == "rejected":
            session.add(
                Notification(
                    user_id=company.id,
                    type="company_registration_rejected",
                    message=request.reason or "",
                    details={"company_id": str(company.id), "reason": request.reason},
                )
            )
        user = session.get(AppUser, company.id)
        assert user is not None
        response = CompanyResponse(
            id=company.id, email=user.email, status=company.status
        )
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
