from sqlalchemy import DateTime, Enum

from app.db.models import AppUser
from tests.db.models.assertions import has_index, has_unique_constraint


def test_email_is_unique() -> None:
    assert has_unique_constraint(AppUser, ["email"])


def test_user_type_uses_enum_and_has_an_index() -> None:
    assert isinstance(AppUser.__table__.c.user_type.type, Enum)
    assert has_index(AppUser, "ix_app_user_user_type")


def test_account_status_defaults_to_active() -> None:
    assert AppUser.__table__.c.account_status.server_default.arg == "active"


def test_email_verification_starts_null_and_keeps_the_time_zone() -> None:
    column = AppUser.__table__.c.email_verified_at

    assert column.nullable is True
    assert column.server_default is None
    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
