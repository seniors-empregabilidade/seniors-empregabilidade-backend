from typing import Literal

from pydantic import BaseModel, ConfigDict


class UpdateJobStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "closed"]
