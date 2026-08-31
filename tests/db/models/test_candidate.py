from app.db.models import Candidate
from tests.db.models.assertions import (
    foreign_key_for,
    has_check_constraint,
    has_unique_constraint,
)


def test_candidate_business_checks_are_declared() -> None:
    assert has_check_constraint(Candidate, "ck_candidate_age_value")
    assert has_check_constraint(Candidate, "ck_candidate_cpf_format")
    assert has_check_constraint(Candidate, "ck_candidate_minimum_age")


def test_cpf_is_unique() -> None:
    assert has_unique_constraint(Candidate, ["cpf"])


def test_user_foreign_key_cascades() -> None:
    assert foreign_key_for(Candidate, "id").ondelete == "CASCADE"


def test_candidate_defaults_are_declared() -> None:
    assert Candidate.__table__.c.availability.server_default.arg == "available"
    assert (
        str(Candidate.__table__.c.accepts_automatic_application.server_default.arg)
        == "false"
    )
