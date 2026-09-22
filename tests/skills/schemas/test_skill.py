import pytest
from pydantic import ValidationError

from app.db.models.enums import SkillType
from app.skills.schemas import SkillRequest


def test_a_typed_name_keeps_its_spelling_without_surrounding_spaces() -> None:
    request = SkillRequest(name="  Gestão de equipes ", type=SkillType.SOFT)

    assert request.name == "Gestão de equipes"


def test_a_name_that_fills_the_column_once_normalized_is_accepted() -> None:
    assert SkillRequest(name="ß" * 50, type=SkillType.HARD).name == "ß" * 50


@pytest.mark.parametrize(
    "name",
    [
        "a" * 99 + "ß",
        "ß" * 100,
        "\N{ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM}" * 10,
        "a" * 99 + "\N{HORIZONTAL ELLIPSIS}",
        "\N{COMBINING ACUTE ACCENT}",
        "\N{ACUTE ACCENT}",
        "\N{ZERO WIDTH SPACE}",
        "Python\x00",
    ],
    ids=[
        "one-over",
        "sharp-s",
        "arabic-ligature",
        "ellipsis",
        "acute",
        "spacing-acute",
        "zero-width-space",
        "nul",
    ],
)
def test_a_name_the_catalog_cannot_compare_is_rejected(name: str) -> None:
    with pytest.raises(ValidationError) as caught:
        SkillRequest(name=name, type=SkillType.HARD)

    assert [error["loc"] for error in caught.value.errors()] == [("name",)]
