from uuid import UUID

from sqlalchemy.orm import Session

from app.companies.schemas.company_profile_response import (
    CompanyAddressResponse,
    CompanyProfileResponse,
)
from app.db.models import Address, Company


def get_company_profile(session: Session, company_id: UUID) -> CompanyProfileResponse:
    return company_profile_response(session, find_company(session, company_id))


def find_company(session: Session, company_id: UUID, *, lock: bool = False) -> Company:
    # `require_approved_company` already proved the company row exists.
    return session.get_one(Company, company_id, with_for_update=lock)


def company_profile_response(
    session: Session, company: Company
) -> CompanyProfileResponse:
    address = session.get(Address, company.address_id) if company.address_id else None
    return CompanyProfileResponse(
        id=company.id,
        cnpj=company.cnpj,
        display_name=company.trade_name,
        legal_name=company.legal_name,
        industry=company.industry,
        address=(
            CompanyAddressResponse(
                street=address.street,
                number=address.number,
                complement=address.complement,
                neighborhood=address.neighborhood,
                city=address.city,
                state=address.state,
                zip_code=address.zip_code,
            )
            if address
            else None
        ),
        contact_email=company.contact_email or company.corporate_email,
        contact_phone=company.contact_phone,
    )
