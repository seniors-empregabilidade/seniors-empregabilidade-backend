from app.db.models import EmailVerificationRequest
from tests.db.models.assertions import foreign_key_for, has_index


def test_user_foreign_key_cascades() -> None:
    assert foreign_key_for(EmailVerificationRequest, "user_id").ondelete == "CASCADE"


def test_rate_limit_lookups_are_indexed() -> None:
    assert has_index(
        EmailVerificationRequest,
        "ix_email_verification_request_user_id_created_at",
    )


def test_the_verification_code_is_never_stored() -> None:
    assert set(EmailVerificationRequest.__table__.c.keys()) == {
        "id",
        "user_id",
        "created_at",
    }
