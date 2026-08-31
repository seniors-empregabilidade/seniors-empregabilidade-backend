from sqlalchemy import Enum

from app.db.models import Skill
from tests.db.models.assertions import has_unique_constraint


def test_name_and_type_pair_is_unique() -> None:
    assert has_unique_constraint(Skill, ["name", "type"])


def test_type_uses_a_postgresql_enum() -> None:
    assert isinstance(Skill.__table__.c.type.type, Enum)
