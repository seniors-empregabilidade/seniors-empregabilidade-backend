from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class AddressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    street: str = Field(min_length=1, max_length=150)
    number: str = Field(min_length=1, max_length=10)
    complement: str | None = Field(default=None, max_length=100)
    neighborhood: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(
        pattern=r"^(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$"
    )
    zip_code: str = Field(min_length=8, max_length=10)

    @field_validator("state", mode="before")
    @classmethod
    def uppercase_state(cls, value: str) -> str:
        return value.upper()

    @field_validator("zip_code")
    @classmethod
    def normalize_zip_code(cls, value: str) -> str:
        normalized = value.replace("-", "")
        if len(normalized) != 8 or not normalized.isascii() or not normalized.isdigit():
            raise ValueError("zip code must contain 8 digits")
        return normalized


class CompanyRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cnpj: str = Field(min_length=14, max_length=18)
    display_name: str = Field(min_length=1, max_length=200)
    address: AddressRequest
    corporate_email: str = Field(
        min_length=3, max_length=150, pattern=r"^[^\s@]+@[^\s@]+$"
    )
    linkedin_url: str | None = Field(default=None, max_length=2048)
    password: SecretStr = Field(min_length=8, max_length=128)
    terms_accepted: bool
    terms_version: str = Field(min_length=1, max_length=20)

    @field_validator("terms_accepted")
    @classmethod
    def require_terms_acceptance(cls, value: bool) -> bool:
        if not value:
            raise ValueError("terms must be accepted")
        return value

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"linkedin.com", "www.linkedin.com"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
            or not parsed.path.startswith("/company/")
            or not parsed.path.removeprefix("/company/").strip("/")
        ):
            raise ValueError("use an HTTPS LinkedIn company URL")
        return value
