from uuid import UUID

from pydantic import BaseModel


class CompanyAddressResponse(BaseModel):
    street: str
    number: str
    complement: str | None
    neighborhood: str
    city: str
    state: str
    zip_code: str


class CompanyProfileResponse(BaseModel):
    id: UUID
    cnpj: str
    display_name: str | None
    legal_name: str
    industry: str | None
    address: CompanyAddressResponse | None
    contact_email: str
    contact_phone: str | None
