from dataclasses import dataclass


class InvalidCpfValueError(ValueError):
    """The supplied value cannot represent a valid Brazilian CPF."""


@dataclass(frozen=True, slots=True)
class Cpf:
    value: str

    @classmethod
    def parse(cls, raw_value: str) -> Cpf:
        digits = raw_value.translate(str.maketrans("", "", ".- "))
        if (
            len(digits) != 11
            or not digits.isascii()
            or not digits.isdigit()
            or digits == digits[0] * 11
        ):
            raise InvalidCpfValueError

        first_digit = _verification_digit(digits[:9], 10)
        second_digit = _verification_digit(f"{digits[:9]}{first_digit}", 11)
        if digits[-2:] != f"{first_digit}{second_digit}":
            raise InvalidCpfValueError

        return cls(digits)


def _verification_digit(digits: str, first_weight: int) -> int:
    total = sum(
        int(digit) * weight
        for digit, weight in zip(digits, range(first_weight, 1, -1), strict=True)
    )
    result = (total * 10) % 11
    return 0 if result == 10 else result
