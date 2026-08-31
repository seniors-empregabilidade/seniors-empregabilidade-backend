from sqlalchemy import Enum

from app.db.models import Training
from tests.db.models.assertions import has_index


def test_training_mode_uses_a_postgresql_enum() -> None:
    assert isinstance(Training.__table__.c.training_mode.type, Enum)


def test_boolean_defaults_and_published_index_are_declared() -> None:
    assert str(Training.__table__.c.free.server_default.arg) == "true"
    assert str(Training.__table__.c.published.server_default.arg) == "false"
    assert has_index(Training, "ix_training_published")
