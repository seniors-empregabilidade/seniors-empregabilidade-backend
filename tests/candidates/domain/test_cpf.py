import pytest

from app.candidates.domain.cpf import Cpf, InvalidCpfValueError


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("11144477735", "11144477735"),
        ("111.444.777-35", "11144477735"),
        ("111 444 777-35", "11144477735"),
    ],
)
def test_valid_cpf_is_normalized(raw_value: str, expected: str) -> None:
    assert Cpf.parse(raw_value).value == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "11144477700",
        "11111111111",
        "123",
        "111a444b77735",
        "\uff11\uff11\uff11\uff14\uff14\uff14\uff17\uff17\uff17\uff13\uff15",
    ],
)
def test_invalid_cpf_is_rejected(raw_value: str) -> None:
    with pytest.raises(InvalidCpfValueError):
        Cpf.parse(raw_value)
