from uuid import UUID

from pydantic import BaseModel


class SimilarJobResponse(BaseModel):
    id: UUID
    title: str
    company_name: str
