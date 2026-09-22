from sqlalchemy import Enum

from app.db.models import Skill
from tests.db.models.assertions import has_unique_constraint


def test_the_normalized_name_identifies_a_catalog_skill() -> None:
    assert has_unique_constraint(Skill, ["normalized_name"])


def test_type_uses_a_postgresql_enum() -> None:
    assert isinstance(Skill.__table__.c.type.type, Enum)
