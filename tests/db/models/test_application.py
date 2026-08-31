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
