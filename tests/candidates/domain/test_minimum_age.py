from datetime import date

from app.candidates.domain.minimum_age import age_on, meets_minimum_age


def test_professional_turning_45_today_is_eligible() -> None:
    today = date(2026, 9, 13)

    assert age_on(date(1981, 9, 13), today) == 45
    assert meets_minimum_age(date(1981, 9, 13), today) is True


def test_professional_turning_45_tomorrow_is_not_eligible() -> None:
    today = date(2026, 9, 13)

    assert age_on(date(1981, 9, 14), today) == 44
    assert meets_minimum_age(date(1981, 9, 14), today) is False
