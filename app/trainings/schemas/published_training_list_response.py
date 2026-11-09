from pydantic import BaseModel, Field

from app.trainings.schemas.published_training_response import (
    PublishedTrainingResponse,
)


class PublishedTrainingListResponse(BaseModel):
    items: list[PublishedTrainingResponse]
    total: int = Field(description="Every published training matching the search.")
