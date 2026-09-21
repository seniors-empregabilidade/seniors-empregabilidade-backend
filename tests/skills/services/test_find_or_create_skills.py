import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Skill
from app.db.models.enums import SkillType
from app.skills.schemas import SkillRequest
from app.skills.services import find_or_create_skills

pytestmark = pytest.mark.integration


def requested(name: str, skill_type: SkillType = SkillType.HARD) -> SkillRequest:
    return SkillRequest(name=name, type=skill_type)


def stored_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Skill)) or 0


def test_a_new_name_becomes_a_catalog_skill(database_session: Session) -> None:
    before = stored_count(database_session)

    found = find_or_create_skills(
        [requested(" Excel  Avançado ")], session=database_session
    )

    assert [skill.name for skill in found] == ["Excel Avançado"]
    assert stored_count(database_session) == before + 1
    stored = database_session.get(Skill, found[0].id)
    assert stored is not None
    assert stored.normalized_name == "excel avancado"


def test_an_existing_name_is_reused_whatever_the_typed_case_or_type(
    database_session: Session,
) -> None:
    existing = find_or_create_skills([requested("NR-11")], session=database_session)
    before = stored_count(database_session)

    found = find_or_create_skills(
        [requested("nr-11", SkillType.SOFT)], session=database_session
    )

    assert found == existing
    assert stored_count(database_session) == before


def test_repeated_names_resolve_to_a_single_skill(database_session: Session) -> None:
    found = find_or_create_skills(
        [requested("Power BI"), requested("power bi"), requested("POWER  BI")],
        session=database_session,
    )

    assert len(found) == 1


def test_the_requested_order_is_preserved(database_session: Session) -> None:
    # Reverse alphabetical on purpose: new skills are inserted in sorted order.
    found = find_or_create_skills(
        [requested("Negociação"), requested("Logística")], session=database_session
    )

    assert [skill.name for skill in found] == ["Negociação", "Logística"]


def test_nothing_requested_creates_nothing(database_session: Session) -> None:
    before = stored_count(database_session)

    assert find_or_create_skills([], session=database_session) == []
    assert stored_count(database_session) == before
