from typing import cast

from sqlalchemy import CHAR, String

from app.db.models import Address


def test_neighborhood_has_the_confirmed_length() -> None:
    neighborhood_type = cast(String, Address.__table__.c.neighborhood.type)

    assert neighborhood_type.length == 100


def test_state_and_zip_code_use_fixed_length_types() -> None:
    assert isinstance(Address.__table__.c.state.type, CHAR)
    assert Address.__table__.c.state.type.length == 2
    assert isinstance(Address.__table__.c.zip_code.type, CHAR)
    assert Address.__table__.c.zip_code.type.length == 8
