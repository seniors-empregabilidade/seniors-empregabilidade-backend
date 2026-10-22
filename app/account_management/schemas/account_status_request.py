from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class AccountStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "blocked"]
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ] = Field(description="Justification recorded in the administrative log.")
