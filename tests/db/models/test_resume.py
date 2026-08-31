from sqlalchemy.sql.sqltypes import ARRAY

from app.db.models import Resume
from tests.db.models.assertions import (
    foreign_key_for,
    has_check_constraint,
    table_for,
)


def test_skill_ids_use_a_postgresql_uuid_array() -> None:
    assert isinstance(Resume.__table__.c.skill_ids.type, ARRAY)


def test_skill_ids_default_to_an_empty_array() -> None:
    assert str(Resume.__table__.c.skill_ids.server_default.arg) == "'{}'::uuid[]"


def test_candidate_relationship_is_unique_indexed_and_cascades() -> None:
    candidate_fk = foreign_key_for(Resume, "candidate_id")

    assert candidate_fk.ondelete == "CASCADE"
    assert candidate_fk.deferrable is True
    candidate_index = next(
        index
        for index in table_for(Resume).indexes
        if index.name == "ix_resume_candidate_id"
    )
    assert candidate_index.unique is True


def test_completion_percentage_is_bounded_and_defaults_to_zero() -> None:
    assert has_check_constraint(Resume, "ck_resume_completion_percentage")
    assert Resume.__table__.c.completion_percentage.server_default.arg == "0"
