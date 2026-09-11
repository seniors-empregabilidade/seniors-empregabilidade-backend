import pytest

from app.companies.domain.exceptions import InvalidCNPJError
from app.companies.domain.value_objects.cnpj import CNPJ


def test_cnpj_normalizes_mask_and_validates_checksum() -> None:
    assert CNPJ("11.222.333/0001-81").value == "11222333000181"


@pytest.mark.parametrize(
    "value", ["123", "00000000000000", "11A22333000181", "11222333000182"]
)
def test_cnpj_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidCNPJError):
        CNPJ(value)
