from datetime import date
from uuid import UUID

from pydantic import BaseModel


class ApplicantCertificationResponse(BaseModel):
    id: UUID
    name: str
    issuer: str | None
    issued_date: date | None
    expiration_date: date | None
