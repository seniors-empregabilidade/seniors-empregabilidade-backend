from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.skills.domain import SkillName
from app.skills.schemas import SkillRequest
from app.skills.services.catalog_skill import CatalogSkill


def find_or_create_skills(
    requested: Sequence[SkillRequest], *, session: Session
) -> list[CatalogSkill]:
    """Resolve typed skills against the catalog, creating the ones it does not have.

    Names that differ only by case, accents or spacing resolve to the same catalog
    entry, and a repeated name is returned once. The caller owns the transaction.
    """
    wanted = _by_normalized_name(requested)
    if not wanted:
        return []

    _create_missing(wanted, session=session)
    catalog = {
        skill.normalized_name: CatalogSkill.of(skill)
        for skill in session.scalars(
            select(Skill).where(Skill.normalized_name.in_(wanted))
        )
    }
    return [catalog[normalized_name] for normalized_name in wanted]


def _by_normalized_name(
    requested: Sequence[SkillRequest],
) -> dict[str, tuple[SkillName, SkillRequest]]:
    wanted: dict[str, tuple[SkillName, SkillRequest]] = {}
    for request in requested:
        name = SkillName.parse(request.name)
        wanted.setdefault(name.normalized, (name, request))
    return wanted


def _create_missing(
    wanted: dict[str, tuple[SkillName, SkillRequest]], *, session: Session
) -> None:
    # A concurrent request may have created the same skill a moment earlier.
    session.execute(
        insert(Skill)
        .values(
            [
                {
                    "name": name.value,
                    "normalized_name": normalized_name,
                    "type": request.type,
                }
                for normalized_name, (name, request) in wanted.items()
            ]
        )
        .on_conflict_do_nothing(index_elements=["normalized_name"])
    )
    session.flush()
