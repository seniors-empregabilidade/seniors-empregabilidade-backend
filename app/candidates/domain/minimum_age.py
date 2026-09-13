from datetime import date

MINIMUM_CANDIDATE_AGE = 45


def age_on(birth_date: date, reference_date: date) -> int:
    birthday_has_passed = (reference_date.month, reference_date.day) >= (
        birth_date.month,
        birth_date.day,
    )
    return reference_date.year - birth_date.year - (not birthday_has_passed)


def meets_minimum_age(birth_date: date, reference_date: date) -> bool:
    return age_on(birth_date, reference_date) >= MINIMUM_CANDIDATE_AGE
