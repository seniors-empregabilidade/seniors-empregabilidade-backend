from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

ExperienceText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
ExperienceDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000)
]


class ExperienceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: ExperienceText
    role: ExperienceText
    start_date: date
    end_date: date | None = None
    description: ExperienceDescription | None = None


class ExperienceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: ExperienceText | None = None
    role: ExperienceText | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: ExperienceDescription | None = None

    @field_validator("company_name", "role", "start_date")
    @classmethod
    def reject_explicit_null(cls, value: str | date | None) -> str | date | None:
        if value is None:
            raise ValueError("This field cannot be cleared.")
        return value
