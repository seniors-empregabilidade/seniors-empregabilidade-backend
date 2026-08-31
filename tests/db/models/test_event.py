from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import Event
from tests.db.models.assertions import foreign_key_for, has_index


def test_user_foreign_key_sets_null_and_is_indexed() -> None:
    user_fk = foreign_key_for(Event, "user_id")

    assert user_fk.ondelete == "SET NULL"
    assert user_fk.deferrable is True
    assert has_index(Event, "ix_event_user_id")


def test_details_use_postgresql_jsonb() -> None:
    assert isinstance(Event.__table__.c.details.type, JSONB)
