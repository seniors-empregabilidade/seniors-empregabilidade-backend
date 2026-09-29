from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class UpdateJobStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "closed"]
    closing_date: Annotated[
        date | None,
        Field(
            description=(
                "New closing date when reopening; the current one is kept when "
                "omitted. Ignored when closing."
            )
        ),
    ] = None
