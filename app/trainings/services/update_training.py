from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Training
from app.trainings.exceptions import TrainingNotFoundError
from app.trainings.schemas import TrainingResponse, TrainingUpdateRequest
from app.trainings.services.describe_trainings import describe_trainings
from app.trainings.services.replace_training_relations import (
    replace_training_jobs,
    replace_training_skills,
)


def update_training(
    session: Session, training_id: UUID, request: TrainingUpdateRequest
) -> TrainingResponse:
    """Change the sent fields of a course; a sent relation set replaces the old one."""
    try:
        training = session.scalar(
            select(Training).where(Training.id == training_id).with_for_update()
        )
        if training is None:
            raise TrainingNotFoundError
        if request.title is not None:
            training.title = request.title
        if request.institution is not None:
            training.provider = request.institution
        if request.mode is not None:
            training.training_mode = request.mode
        if request.external_link is not None:
            training.external_link = request.external_link
        if request.published is not None:
            training.published = request.published
        if request.skill_ids is not None:
            replace_training_skills(session, training.id, request.skill_ids)
        if request.job_ids is not None:
            replace_training_jobs(session, training.id, request.job_ids)
        training.updated_at = func.now()
        session.flush()
        session.refresh(training)
        response = describe_trainings(session, [training])[0]
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
