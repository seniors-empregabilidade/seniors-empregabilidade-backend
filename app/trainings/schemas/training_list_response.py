from pydantic import BaseModel, Field

from app.trainings.schemas.training_response import TrainingResponse


class TrainingListResponse(BaseModel):
    items: list[TrainingResponse]
    total: int = Field(description="Every training matching the filters.")
