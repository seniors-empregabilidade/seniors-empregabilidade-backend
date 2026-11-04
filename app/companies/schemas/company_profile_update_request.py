from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.companies.schemas.company_request import AddressRequest


class CompanyProfileUpdateRequest(BaseModel):
    """Full replacement of the editable profile, as the edit modal sends it.

    `cnpj` is accepted only so a client may echo the stored value; any other
    value is rejected by the service. Optional fields left out are cleared.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cnpj: str | None = Field(default=None, max_length=18)
    display_name: str = Field(min_length=1, max_length=200)
    legal_name: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=100)
    address: AddressRequest
    contact_email: str = Field(
        min_length=3, max_length=150, pattern=r"^[^\s@]+@[^\s@]+$"
    )
    contact_phone: str | None = Field(
        default=None, max_length=20, pattern=r"^\+?[0-9 ()-]{7,20}$"
    )

    @field_validator("industry", "contact_phone", mode="before")
    @classmethod
    def blank_as_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
