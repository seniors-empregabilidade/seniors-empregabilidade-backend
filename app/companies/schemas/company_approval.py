from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanyApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
