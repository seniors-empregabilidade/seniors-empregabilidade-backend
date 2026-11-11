from uuid import UUID

from pydantic import BaseModel


class TrainingJobResponse(BaseModel):
    """A job related to a course, named so the course editor can show it."""

    id: UUID
    title: str
