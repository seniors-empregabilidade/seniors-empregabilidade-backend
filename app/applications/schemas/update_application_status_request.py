from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Statuses the company can set: a candidate cannot be moved back to "applied"
# by a company action, and withdrawn/expired are candidate-side or system outcomes.
CompanyApplicationStatus = Literal[
    "under_review",
    "in_selection_process",
    "hired",
    "not_selected",
]

Reason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class UpdateApplicationStatusRequest(BaseModel):
    """Company-side action on a candidate's application.

    ``reason`` is required only when setting ``status`` to ``not_selected``.
    It will be shown to the candidate (US-13) so it must be meaningful.
    """

    model_config = ConfigDict(extra="forbid")

    status: CompanyApplicationStatus
    reason: Reason | None = Field(
        default=None,
        description=("Required when status is 'not_selected'. Shown to the candidate."),
    )

    @model_validator(mode="after")
    def reason_required_for_not_selected(self) -> UpdateApplicationStatusRequest:
        if self.status == "not_selected" and not self.reason:
            raise ValueError("reason is required when status is 'not_selected'")
        return self
