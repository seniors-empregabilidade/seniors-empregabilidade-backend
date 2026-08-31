from sqlalchemy import Enum

from app.db.models import AppUser
from tests.db.models.assertions import has_index, has_unique_constraint


def test_email_is_unique() -> None:
    assert has_unique_constraint(AppUser, ["email"])


def test_user_type_uses_enum_and_has_an_index() -> None:
    assert isinstance(AppUser.__table__.c.user_type.type, Enum)
    assert has_index(AppUser, "ix_app_user_user_type")


def test_account_status_defaults_to_active() -> None:
    assert AppUser.__table__.c.account_status.server_default.arg == "active"
