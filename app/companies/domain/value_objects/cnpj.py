from dataclasses import dataclass

from app.companies.domain.exceptions import InvalidCNPJError


@dataclass(frozen=True, slots=True)
class CNPJ:
    value: str

    def __init__(self, raw_value: str) -> None:
        normalized = raw_value.translate(str.maketrans("", "", ".-/"))
        if not normalized.isascii() or not normalized.isdigit():
            raise InvalidCNPJError
        if len(normalized) != 14 or len(set(normalized)) == 1:
            raise InvalidCNPJError
        if normalized[-2:] != self._check_digits(normalized[:12]):
            raise InvalidCNPJError
        object.__setattr__(self, "value", normalized)

    @staticmethod
    def _check_digits(base: str) -> str:
        digits = base
        for weights in (
            (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
            (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
        ):
            total = sum(
                int(digit) * weight
                for digit, weight in zip(digits, weights, strict=True)
            )
            remainder = total % 11
            digits += str(0 if remainder < 2 else 11 - remainder)
        return digits[-2:]
