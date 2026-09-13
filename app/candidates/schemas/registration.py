from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
)

TrimmedName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
TrimmedPhone = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=7, max_length=20)
]
OptionalCity = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
OptionalState = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=2, max_length=2),
]
TermsVersion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]


class ProfessionalRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: TrimmedName
    cpf: str = Field(min_length=11, max_length=14)
    birth_date: date
    phone: TrimmedPhone
    email: EmailStr = Field(max_length=150)
    password: SecretStr = Field(min_length=1, max_length=256)
    terms_version_accepted: TermsVersion | None = None
    city: OptionalCity | None = None
    state: OptionalState | None = None


class ProfessionalRegistrationResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    email_verification_required: bool
