from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Skill, Training, TrainingJob, TrainingSkill
from app.skills.schemas import SkillResponse
from app.trainings.schemas import PublishedTrainingResponse, TrainingResponse


def describe_trainings(
    session: Session, trainings: Sequence[Training]
) -> list[TrainingResponse]:
    """Build the administrative view of trainings with their skills and jobs."""
    ids = [training.id for training in trainings]
    skills = _skills_by_training(session, ids)
    jobs = _job_ids_by_training(session, ids)
    return [
        TrainingResponse(
            id=training.id,
            title=training.title,
            institution=training.provider,
            mode=training.training_mode,
            external_link=training.external_link,
            published=training.published,
            skills=skills[training.id],
            job_ids=jobs[training.id],
        )
        for training in trainings
    ]


def describe_published_trainings(
    session: Session, trainings: Sequence[Training]
) -> list[PublishedTrainingResponse]:
    """Build the candidate view of trainings, without the related jobs."""
    skills = _skills_by_training(session, [training.id for training in trainings])
    return [
        PublishedTrainingResponse(
            id=training.id,
            title=training.title,
            institution=training.provider,
            mode=training.training_mode,
            external_link=training.external_link,
            skills=skills[training.id],
        )
        for training in trainings
    ]


def _skills_by_training(
    session: Session, training_ids: Sequence[UUID]
) -> defaultdict[UUID, list[SkillResponse]]:
    by_training: defaultdict[UUID, list[SkillResponse]] = defaultdict(list)
    rows = session.execute(
        select(TrainingSkill.training_id, Skill)
        .join(Skill, Skill.id == TrainingSkill.skill_id)
        .where(TrainingSkill.training_id.in_(training_ids))
        .order_by(Skill.name, Skill.id)
    )
    for training_id, skill in rows:
        by_training[training_id].append(
            SkillResponse(id=skill.id, name=skill.name, type=skill.type)
        )
    return by_training


def _job_ids_by_training(
    session: Session, training_ids: Sequence[UUID]
) -> defaultdict[UUID, list[UUID]]:
    by_training: defaultdict[UUID, list[UUID]] = defaultdict(list)
    rows = session.execute(
        select(TrainingJob.training_id, TrainingJob.job_id)
        .where(TrainingJob.training_id.in_(training_ids))
        .order_by(TrainingJob.job_id)
    )
    for training_id, job_id in rows:
        by_training[training_id].append(job_id)
    return by_training
