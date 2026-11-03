from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

MAX_MESSAGE_LENGTH = 2000


class CreateContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    candidate_id: UUID
    message: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH
        ),
    ]
