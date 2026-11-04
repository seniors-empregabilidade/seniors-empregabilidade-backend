import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.companies.domain.exceptions import CNPJReadOnlyError
from app.companies.domain.value_objects.corporate_email import CorporateEmail
from app.companies.schemas.company_profile_response import CompanyProfileResponse
from app.companies.schemas.company_profile_update_request import (
    CompanyProfileUpdateRequest,
)
from app.companies.services.get_company_profile import (
    company_profile_response,
    find_company,
)
from app.db.models import Address, Company


def update_company_profile(
    session: Session,
    company_id: UUID,
    request: CompanyProfileUpdateRequest,
    *,
    personal_email_domains: frozenset[str],
) -> CompanyProfileResponse:
    """Replace the editable profile of the authenticated company (US-30).

    The CNPJ, the login e-mail (`app_user.email` and `corporate_email`) and the
    approval status are never changed here. Jobs read the company name live, so
    they show the new name as soon as this commits.
    """
    try:
        company = find_company(session, company_id, lock=True)
        if request.cnpj is not None and re.sub(r"\D", "", request.cnpj) != company.cnpj:
            raise CNPJReadOnlyError
        contact_email = CorporateEmail(request.contact_email, personal_email_domains)

        company.trade_name = request.display_name
        company.legal_name = request.legal_name
        company.industry = request.industry
        company.contact_email = contact_email.value
        company.contact_phone = request.contact_phone
        _replace_address(session, company, request)

        session.flush()
        profile = company_profile_response(session, company)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return profile


def _replace_address(
    session: Session, company: Company, request: CompanyProfileUpdateRequest
) -> None:
    address = session.get(Address, company.address_id) if company.address_id else None
    if address is None:
        address = Address()
        session.add(address)
    values = request.address
    address.street = values.street
    address.number = values.number
    address.complement = values.complement or None
    address.neighborhood = values.neighborhood
    address.city = values.city
    address.state = values.state
    address.zip_code = values.zip_code
    session.flush()
    company.address_id = address.id
