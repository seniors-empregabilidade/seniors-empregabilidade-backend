from sqlalchemy.sql.sqltypes import ARRAY

from app.db.models import Resume


def test_skill_ids_use_a_postgresql_uuid_array() -> None:
    assert isinstance(Resume.__table__.c.skill_ids.type, ARRAY)


def test_skill_ids_default_to_an_empty_array() -> None:
    assert str(Resume.__table__.c.skill_ids.server_default.arg) == "'{}'::uuid[]"
