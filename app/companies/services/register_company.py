from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.companies.domain.policies.cnae_policy import ensure_cnae_is_allowed
from app.companies.domain.value_objects.cnpj import CNPJ
from app.companies.domain.value_objects.corporate_email import CorporateEmail
from app.companies.integrations.brasil_api import CompanyRegistry
from app.companies.schemas.company_request import CompanyRegistrationRequest
from app.companies.schemas.company_response import CompanyResponse
from app.core.passwords import hash_password
from app.db.models import Address, AppUser, Company
from app.db.models.enums import CompanyStatus, UserType


class CompanyCNPJConflictError(Exception):
    pass


class CompanyEmailConflictError(Exception):
    pass


def register_company(
    request: CompanyRegistrationRequest,
    *,
    session: Session,
    registry: CompanyRegistry,
    blocked_cnae_prefixes: tuple[str, ...],
    personal_email_domains: frozenset[str],
) -> CompanyResponse:
    cnpj = CNPJ(request.cnpj)
    email = CorporateEmail(str(request.corporate_email), personal_email_domains)
    record = registry.get_record(cnpj.value)
    ensure_cnae_is_allowed(record.primary_cnae, blocked_cnae_prefixes)

    address = Address(
        street=request.address.street,
        number=request.address.number,
        complement=request.address.complement,
        neighborhood=request.address.neighborhood,
        city=request.address.city,
        state=request.address.state,
        zip_code=request.address.zip_code,
        code=None,
    )
    user = AppUser(
        email=email.value,
        password_hash=hash_password(request.password.get_secret_value()),
        user_type=UserType.COMPANY,
    )
    try:
        session.add_all((address, user))
        session.flush()
        company = Company(
            id=user.id,
            cnpj=cnpj.value,
            legal_name=record.legal_name,
            trade_name=request.display_name,
            primary_cnae=record.primary_cnae,
            corporate_email=email.value,
            address_id=address.id,
            status=CompanyStatus.PENDING,
            terms_version_accepted=request.terms_version,
            terms_accepted_at=datetime.now(UTC),
        )
        session.add(company)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", "")
        if constraint == "uq_company_cnpj":
            raise CompanyCNPJConflictError from exc
        if constraint in {"uq_app_user_email", "uq_company_corporate_email"}:
            raise CompanyEmailConflictError from exc
        raise
    except Exception:
        session.rollback()
        raise
    return CompanyResponse(id=user.id, email=user.email, status=company.status)
