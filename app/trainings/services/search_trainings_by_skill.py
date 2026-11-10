from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models import Skill, Training, TrainingSkill
from app.skills.domain import normalize_skill_name
from app.skills.services.search_skills import could_be_stored
from app.trainings.schemas import PublishedTrainingListResponse
from app.trainings.services.describe_trainings import describe_published_trainings


def search_trainings_by_skill(
    session: Session,
    *,
    skill: str | None,
    skill_id: UUID | None,
    limit: int,
    offset: int,
) -> PublishedTrainingListResponse:
    """List published trainings that teach a skill, ignoring case and accents.

    ``skill`` matches any catalog skill whose name contains the text, and
    ``skill_id`` matches one exact skill; when both are sent a training must
    satisfy both. Without either, every published training is listed. A text no
    stored name could contain finds nothing instead of reaching the database.
    """
    conditions: list[ColumnElement[bool]] = [Training.published.is_(True)]
    term = normalize_skill_name(skill) if skill is not None else ""
    if term:
        if not could_be_stored(term):
            return PublishedTrainingListResponse(items=[], total=0)
        conditions.append(
            Training.id.in_(
                select(TrainingSkill.training_id)
                .join(Skill, Skill.id == TrainingSkill.skill_id)
                .where(Skill.normalized_name.contains(term, autoescape=True))
            )
        )
    if skill_id is not None:
        conditions.append(
            Training.id.in_(
                select(TrainingSkill.training_id).where(
                    TrainingSkill.skill_id == skill_id
                )
            )
        )

    total = session.scalar(
        select(func.count()).select_from(Training).where(*conditions)
    )
    trainings = session.scalars(
        select(Training)
        .where(*conditions)
        .order_by(Training.title, Training.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return PublishedTrainingListResponse(
        items=describe_published_trainings(session, trainings), total=total or 0
    )
