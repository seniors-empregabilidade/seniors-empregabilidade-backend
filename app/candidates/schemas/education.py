from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

InstitutionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
EducationDetail = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class EducationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: InstitutionName
    degree: EducationDetail | None = None
    field: EducationDetail | None = None
    start_date: date | None = None
    end_date: date | None = None


class EducationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: InstitutionName | None = None
    degree: EducationDetail | None = None
    field: EducationDetail | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("institution")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This field cannot be cleared.")
        return value
