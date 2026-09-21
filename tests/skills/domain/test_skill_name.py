import pytest

from app.skills.domain import InvalidSkillNameError, SkillName


def test_display_value_keeps_the_original_letters() -> None:
    assert SkillName.parse("Excel Avançado").value == "Excel Avançado"


def test_surrounding_and_repeated_spaces_are_removed() -> None:
    assert SkillName.parse("  Gestão   de equipes ").value == "Gestão de equipes"


@pytest.mark.parametrize(
    "other",
    ["excel avançado", "EXCEL AVANÇADO", " Excel  Avancado ", "excel avancado"],
)
def test_case_spacing_and_accents_do_not_create_another_skill(other: str) -> None:
    assert (
        SkillName.parse(other).normalized
        == SkillName.parse("Excel Avançado").normalized
    )


def test_different_names_remain_different() -> None:
    assert SkillName.parse("Excel").normalized != SkillName.parse("Power BI").normalized


@pytest.mark.parametrize("raw_value", ["", "   ", "\n\t"])
def test_a_blank_name_is_rejected(raw_value: str) -> None:
    with pytest.raises(InvalidSkillNameError):
        SkillName.parse(raw_value)


def test_a_name_longer_than_the_column_is_rejected() -> None:
    with pytest.raises(InvalidSkillNameError):
        SkillName.parse("a" * 101)


def test_a_name_that_fills_the_column_once_normalized_is_accepted() -> None:
    assert len(SkillName.parse("ß" * 50).normalized) == 100


@pytest.mark.parametrize(
    "raw_value",
    [
        "ß" * 100,
        "\N{ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM}" * 10,
        "a" * 99 + "\N{HORIZONTAL ELLIPSIS}",
    ],
    ids=["sharp-s", "arabic-ligature", "ellipsis"],
)
def test_a_name_that_outgrows_the_column_once_normalized_is_rejected(
    raw_value: str,
) -> None:
    with pytest.raises(InvalidSkillNameError):
        SkillName.parse(raw_value)


@pytest.mark.parametrize(
    "raw_value",
    [
        "\N{COMBINING ACUTE ACCENT}",
        "\N{COMBINING GRAVE ACCENT}",
        "\N{COMBINING ACUTE ACCENT}\N{COMBINING GRAVE ACCENT}",
        "\N{ACUTE ACCENT}",
        "\N{DIAERESIS} \N{ACUTE ACCENT}",
    ],
    ids=["acute", "grave", "two-marks", "spacing-acute", "spacing-marks"],
)
def test_a_name_made_only_of_accents_is_rejected(raw_value: str) -> None:
    with pytest.raises(InvalidSkillNameError):
        SkillName.parse(raw_value)


@pytest.mark.parametrize(
    "other",
    [
        "Java\N{ACUTE ACCENT}",
        "Java \N{ACUTE ACCENT}",
        "\N{DIAERESIS}Java",
        "Ja\N{ZERO WIDTH SPACE}va",
        "Java\N{SOFT HYPHEN}",
    ],
    ids=[
        "trailing-accent",
        "spaced-accent",
        "leading-accent",
        "zero-width",
        "soft-hyphen",
    ],
)
def test_loose_accents_and_invisible_characters_do_not_create_another_skill(
    other: str,
) -> None:
    assert SkillName.parse(other).normalized == SkillName.parse("Java").normalized


@pytest.mark.parametrize(
    "raw_value",
    ["\N{ZERO WIDTH SPACE}", "\N{WORD JOINER}\N{ZERO WIDTH NO-BREAK SPACE}"],
    ids=["zero-width-space", "joiners"],
)
def test_a_name_made_only_of_invisible_characters_is_rejected(raw_value: str) -> None:
    with pytest.raises(InvalidSkillNameError):
        SkillName.parse(raw_value)


@pytest.mark.parametrize(
    "raw_value",
    ["\x00", "Python\x00", "Py\x07thon"],
    ids=["nul", "trailing-nul", "bell"],
)
def test_a_name_with_a_control_character_is_rejected(raw_value: str) -> None:
    with pytest.raises(InvalidSkillNameError):
        SkillName.parse(raw_value)
