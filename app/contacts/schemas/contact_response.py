from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import EmailDeliveryStatus


class ContactResponse(BaseModel):
    id: UUID
    job_id: UUID
    candidate_id: UUID
    created_at: datetime
    email_status: EmailDeliveryStatus
