from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Training, TrainingSkill
from app.trainings.schemas import TrainingListResponse
from app.trainings.services.describe_trainings import describe_trainings


def list_trainings(
    session: Session,
    *,
    search: str | None,
    skill_id: UUID | None,
    published: bool | None,
    limit: int,
    offset: int,
) -> TrainingListResponse:
    """List every training, unpublished ones included, for its administration."""
    conditions: list[ColumnElement[bool]] = []
    term = search.strip() if search is not None else ""
    if term:
        conditions.append(
            or_(
                Training.title.icontains(term, autoescape=True),
                Training.provider.icontains(term, autoescape=True),
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
    if published is not None:
        conditions.append(Training.published.is_(published))

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
    return TrainingListResponse(
        items=describe_trainings(session, trainings), total=total or 0
    )
