from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompanyApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def require_rejection_reason(self) -> CompanyApprovalRequest:
        if self.status == "rejected" and not self.reason:
            raise ValueError("a reason is required when rejecting a company")
        if self.status == "approved" and self.reason is not None:
            raise ValueError("a reason is only accepted when rejecting a company")
        return self
