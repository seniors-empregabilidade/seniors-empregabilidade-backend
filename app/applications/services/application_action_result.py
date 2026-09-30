from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.db.models.enums import ApplicationStatus


@dataclass(frozen=True, slots=True)
class ApplicationActionResult:
    """Output of a company-side application status change.

    Application-layer value, not an HTTP DTO. The router maps it to the
    appropriate response schema.
    """

    application_id: UUID
    job_id: UUID
    candidate_id: UUID
    status: ApplicationStatus
    updated_at: datetime
