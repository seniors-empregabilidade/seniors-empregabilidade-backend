from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.db.models import Job, Skill, TrainingJob, TrainingSkill
from app.trainings.exceptions import TrainingRelationNotFoundError


def replace_training_skills(
    session: Session, training_id: UUID, skill_ids: Sequence[UUID]
) -> None:
    """Make the given skills the only ones the training teaches."""
    existing = session.scalar(
        select(func.count()).select_from(Skill).where(Skill.id.in_(skill_ids))
    )
    if existing != len(set(skill_ids)):
        raise TrainingRelationNotFoundError("skill_ids")
    session.execute(
        delete(TrainingSkill).where(TrainingSkill.training_id == training_id)
    )
    if skill_ids:
        session.execute(
            insert(TrainingSkill),
            [{"training_id": training_id, "skill_id": id_} for id_ in skill_ids],
        )


def replace_training_jobs(
    session: Session, training_id: UUID, job_ids: Sequence[UUID]
) -> None:
    """Make the given jobs the only ones the training is linked to."""
    existing = session.scalar(
        select(func.count()).select_from(Job).where(Job.id.in_(job_ids))
    )
    if existing != len(set(job_ids)):
        raise TrainingRelationNotFoundError("job_ids")
    session.execute(delete(TrainingJob).where(TrainingJob.training_id == training_id))
    if job_ids:
        session.execute(
            insert(TrainingJob),
            [{"training_id": training_id, "job_id": id_} for id_ in job_ids],
        )
