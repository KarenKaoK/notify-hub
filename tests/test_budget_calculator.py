from datetime import datetime
from decimal import Decimal

import pytest

from budget_calculator import (
    ValidationError,
    calculate_budget,
    format_eur,
    money,
)


CATEGORIES = {
    "交": 126,
    "食": 372.14,
    "日": 167.51,
    "住": 0,
    "保險": 5.8,
    "運": 64.97,
}


@pytest.mark.parametrize(
    ("day", "expected_week", "expected_allowance"),
    [
        (1, 1, "100.00"),
        (7, 1, "100.00"),
        (8, 2, "200.00"),
        (14, 2, "200.00"),
        (15, 3, "300.00"),
        (21, 3, "300.00"),
        (22, 4, "400.00"),
        (28, 4, "400.00"),
        (29, 4, "400.00"),
        (31, 4, "400.00"),
    ],
)
def test_week_boundaries(day, expected_week, expected_allowance):
    result = calculate_budget(CATEGORIES, datetime(2026, 1, day))
    assert result.week_number == expected_week
    assert result.cumulative_allowance == Decimal(expected_allowance)


def test_confirmed_budget_example():
    result = calculate_budget(CATEGORIES, datetime(2026, 6, 21))
    assert result.monthly_remaining == Decimal("-198.42")
    assert result.cumulative_spent == Decimal("539.65")
    assert result.weekly_remaining == Decimal("-239.65")


def test_accepts_future_categories_without_code_changes():
    categories = dict(CATEGORIES)
    categories["醫療"] = 12.34
    result = calculate_budget(categories, datetime(2026, 6, 21))
    assert result.categories["醫療"] == Decimal("12.34")
    assert result.monthly_remaining == Decimal("-210.76")
    assert result.cumulative_spent == Decimal("539.65")


def test_missing_weekly_categories_count_as_zero():
    result = calculate_budget({"住": 500}, datetime(2026, 6, 21))
    assert result.monthly_remaining == Decimal("38.00")
    assert result.cumulative_spent == Decimal("0.00")
    assert result.weekly_remaining == Decimal("300.00")


def test_money_rounds_half_up_to_cents():
    assert money("1.005", "amount") == Decimal("1.01")
    assert money("1.004", "amount") == Decimal("1.00")
    assert format_eur(Decimal("-1.2")) == "-€1.20"


@pytest.mark.parametrize("value", [None, True, "not-a-number", "NaN", "Infinity"])
def test_money_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        money(value, "amount")


def test_requires_non_empty_categories():
    with pytest.raises(ValidationError, match="must not be empty"):
        calculate_budget({}, datetime(2026, 6, 21))
