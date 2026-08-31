from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import Notification
from tests.db.models.assertions import foreign_key_for, table_for


def test_user_foreign_key_cascades() -> None:
    user_fk = foreign_key_for(Notification, "user_id")

    assert user_fk.ondelete == "CASCADE"
    assert user_fk.deferrable is True


def test_user_and_read_index_is_declared() -> None:
    index = next(
        index
        for index in table_for(Notification).indexes
        if index.name == "ix_notification_user_id_read"
    )

    assert [column.name for column in index.columns] == ["user_id", "read"]


def test_details_use_jsonb_and_read_defaults_to_false() -> None:
    assert isinstance(Notification.__table__.c.details.type, JSONB)
    assert str(Notification.__table__.c.read.server_default.arg) == "false"
