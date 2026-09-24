from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
