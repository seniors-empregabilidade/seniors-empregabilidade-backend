from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, Skill, Training, TrainingJob, TrainingSkill
from app.skills.schemas import SkillResponse
from app.trainings.schemas import (
    PublishedTrainingResponse,
    TrainingJobResponse,
    TrainingResponse,
)


def describe_trainings(
    session: Session, trainings: Sequence[Training]
) -> list[TrainingResponse]:
    """Build the administrative view of trainings with their skills and jobs.

    ``jobs`` names the related jobs, ordered by title, for the course editor;
    ``job_ids`` keeps the ids in their usual order.
    """
    ids = [training.id for training in trainings]
    skills = _skills_by_training(session, ids)
    jobs = _jobs_by_training(session, ids)
    return [
        TrainingResponse(
            id=training.id,
            title=training.title,
            institution=training.provider,
            mode=training.training_mode,
            external_link=training.external_link,
            published=training.published,
            skills=skills[training.id],
            job_ids=sorted(job.id for job in jobs[training.id]),
            jobs=jobs[training.id],
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


def _jobs_by_training(
    session: Session, training_ids: Sequence[UUID]
) -> defaultdict[UUID, list[TrainingJobResponse]]:
    by_training: defaultdict[UUID, list[TrainingJobResponse]] = defaultdict(list)
    rows = session.execute(
        select(TrainingJob.training_id, Job.id, Job.title)
        .join(Job, Job.id == TrainingJob.job_id)
        .where(TrainingJob.training_id.in_(training_ids))
        .order_by(Job.title, Job.id)
    )
    for training_id, job_id, title in rows:
        by_training[training_id].append(TrainingJobResponse(id=job_id, title=title))
    return by_training
