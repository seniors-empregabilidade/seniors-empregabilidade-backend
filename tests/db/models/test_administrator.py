from app.db.models import Administrator
from tests.db.models.assertions import foreign_key_for


def test_user_foreign_key_cascades_and_is_deferrable() -> None:
    user_fk = foreign_key_for(Administrator, "id")

    assert user_fk.ondelete == "CASCADE"
    assert user_fk.deferrable is True
    assert user_fk.initially == "IMMEDIATE"


def test_active_defaults_to_true() -> None:
    assert str(Administrator.__table__.c.active.server_default.arg) == "true"
