def _only_digits(value: str) -> str:
    return "".join(filter(str.isdigit, value))


def validate_cpf(cpf: str) -> bool:
    """Validate a Brazilian CPF number.
    The algorithm:
    1. Remove non‑digit characters.
    2. CPF must have 11 digits and cannot be a sequence of equal digits.
    3. Calculate first verification digit using weight 10..2.
    4. Calculate second verification digit using weight 11..2 (including first digit).
    5. Compare calculated digits with the last two digits of the CPF.
    """
    numbers = _only_digits(cpf)
    if len(numbers) != 11:
        return False
    if numbers == numbers[0] * 11:
        return False
    sum1 = sum(int(d) * w for d, w in zip(numbers[:9], range(10, 1, -1)))
    dig1 = (sum1 * 10) % 11
    dig1 = 0 if dig1 == 10 else dig1
    sum2 = sum(int(d) * w for d, w in zip(numbers[:9] + str(dig1), range(11, 1, -1)))
    dig2 = (sum2 * 10) % 11
    dig2 = 0 if dig2 == 10 else dig2
    return numbers[-2:] == f"{dig1}{dig2}"
