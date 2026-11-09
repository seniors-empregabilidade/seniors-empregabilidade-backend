from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Training
from app.trainings.exceptions import TrainingNotFoundError


def delete_training(session: Session, training_id: UUID) -> None:
    """Remove a course; its links to skills and jobs go with it."""
    try:
        deleted = session.execute(
            delete(Training).where(Training.id == training_id).returning(Training.id)
        ).first()
        if deleted is None:
            raise TrainingNotFoundError
        session.commit()
    except Exception:
        session.rollback()
        raise
