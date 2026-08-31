from typing import cast

from sqlalchemy import String

from app.db.models import Address


def test_neighborhood_has_the_confirmed_length() -> None:
    neighborhood_type = cast(String, Address.__table__.c.neighborhood.type)

    assert neighborhood_type.length == 100
