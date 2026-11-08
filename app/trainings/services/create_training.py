from sqlalchemy.orm import Session

from app.db.models import Training
from app.trainings.schemas import TrainingRequest, TrainingResponse
from app.trainings.services.describe_trainings import describe_trainings
from app.trainings.services.replace_training_relations import (
    replace_training_jobs,
    replace_training_skills,
)


def create_training(session: Session, request: TrainingRequest) -> TrainingResponse:
    """Add a course with its relations in one transaction."""
    try:
        training = Training(
            title=request.title,
            provider=request.institution,
            training_mode=request.mode,
            external_link=request.external_link,
            published=request.published,
        )
        session.add(training)
        session.flush()
        replace_training_skills(session, training.id, request.skill_ids)
        replace_training_jobs(session, training.id, request.job_ids)
        response = describe_trainings(session, [training])[0]
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
