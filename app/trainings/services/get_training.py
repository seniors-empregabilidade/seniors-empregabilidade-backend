from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Training
from app.trainings.exceptions import TrainingNotFoundError
from app.trainings.schemas import TrainingResponse
from app.trainings.services.describe_trainings import describe_trainings


def get_training(session: Session, training_id: UUID) -> TrainingResponse:
    training = session.get(Training, training_id)
    if training is None:
        raise TrainingNotFoundError
    return describe_trainings(session, [training])[0]
