from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GuidanceResponse(BaseModel):
    id: UUID
    note: str
    created_at: datetime
    administrator_name: str
