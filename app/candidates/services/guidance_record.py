from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GuidanceRecord:
    id: UUID
    note: str
    created_at: datetime
    administrator_name: str
