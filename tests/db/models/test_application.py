from app.db.models import Application
from tests.db.models.assertions import (
    foreign_key_for,
    has_check_constraint,
    has_unique_constraint,
)


def test_candidate_and_job_pair_is_unique() -> None:
    assert has_unique_constraint(Application, ["candidate_id", "job_id"])


def test_match_score_is_bounded() -> None:
    assert has_check_constraint(Application, "ck_application_match_score")


def test_parent_foreign_keys_cascade() -> None:
    assert foreign_key_for(Application, "candidate_id").ondelete == "CASCADE"
    assert foreign_key_for(Application, "job_id").ondelete == "CASCADE"


def test_application_defaults_are_declared() -> None:
    assert Application.__table__.c.type.server_default.arg == "active"
    assert Application.__table__.c.status.server_default.arg == "applied"


def test_closed_at_is_nullable() -> None:
    assert Application.__table__.c.closed_at.nullable is True


def test_requirements_range_is_bounded() -> None:
    assert has_check_constraint(Application, "ck_application_requirements_range")


def test_requirement_counts_are_nullable() -> None:
    assert Application.__table__.c.matched_requirements.nullable is True
    assert Application.__table__.c.total_requirements.nullable is True
