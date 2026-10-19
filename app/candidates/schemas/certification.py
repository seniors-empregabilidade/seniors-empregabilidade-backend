from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

CertificationText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]


class CertificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CertificationText
    issuer: CertificationText | None = None
    issued_date: date | None = None
    expiration_date: date | None = None


class CertificationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CertificationText | None = None
    issuer: CertificationText | None = None
    issued_date: date | None = None
    expiration_date: date | None = None

    @field_validator("name")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This field cannot be cleared.")
        return value


class CertificationDocumentLinkResponse(BaseModel):
    url: str
    expires_at: datetime
