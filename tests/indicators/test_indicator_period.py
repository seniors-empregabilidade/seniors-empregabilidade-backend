from datetime import UTC, date, datetime

from app.db.models import AppUser
from app.indicators.schemas.indicator_filters import IndicatorFilters
from app.indicators.services.platform_indicators import (
    _ensure_valid_period,
    _Period,
    _period_of,
    _within,
)


def test_period_with_only_start_date_has_no_upper_bound() -> None:
    period = _period_of(IndicatorFilters(start_date=date(2001, 2, 1)))

    assert period.start == datetime(2001, 2, 1, 2, tzinfo=UTC)
    assert period.end is None


def test_period_with_only_end_date_has_no_lower_bound() -> None:
    period = _period_of(IndicatorFilters(end_date=date(2001, 1, 31)))

    assert period.start is None
    assert period.end == datetime(2001, 2, 1, 1, 59, 59, 999999, tzinfo=UTC)


def test_open_period_adds_no_conditions() -> None:
    conditions = _within(AppUser.created_at, _Period(start=None, end=None))

    assert conditions == []


def test_each_period_bound_adds_one_condition() -> None:
    start_only = _Period(start=datetime(2001, 2, 1, tzinfo=UTC), end=None)
    end_only = _Period(start=None, end=datetime(2001, 2, 1, tzinfo=UTC))

    assert len(_within(AppUser.created_at, start_only)) == 1
    assert len(_within(AppUser.created_at, end_only)) == 1


def test_validation_accepts_a_single_date() -> None:
    _ensure_valid_period(IndicatorFilters(start_date=date(2001, 2, 1)))
    _ensure_valid_period(IndicatorFilters(end_date=date(2001, 1, 31)))
