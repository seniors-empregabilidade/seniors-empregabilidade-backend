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
