from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints


class GuidanceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ]


class GuidanceResponse(BaseModel):
    id: UUID
    note: str
    created_at: datetime
    administrator_name: str
