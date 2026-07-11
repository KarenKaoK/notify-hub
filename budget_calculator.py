"""Budget calculations and Telegram message formatting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping


WEEKLY_SPENDING_CATEGORIES = ("日", "食")
MONTHLY_BUDGET = Decimal("538.00")
WEEKLY_ALLOWANCE = Decimal("100.00")
CENT = Decimal("0.01")


class ValidationError(ValueError):
    """Raised when notification data does not match the API contract."""


@dataclass(frozen=True)
class BudgetResult:
    categories: dict[str, Decimal]
    monthly_remaining: Decimal
    week_number: int
    cumulative_allowance: Decimal
    cumulative_spent: Decimal
    weekly_remaining: Decimal


def money(value: object, field_name: str) -> Decimal:
    """Convert an API value to euro cents using round-half-up."""
    if isinstance(value, bool) or value is None:
        raise ValidationError(f"{field_name} must be a number")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{field_name} must be a number") from None
    if not amount.is_finite():
        raise ValidationError(f"{field_name} must be a finite number")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_budget(categories: Mapping[str, object], now: datetime) -> BudgetResult:
    if not isinstance(categories, Mapping):
        raise ValidationError("categories must be an object")

    if not categories:
        raise ValidationError("categories must not be empty")

    parsed: dict[str, Decimal] = {}
    for raw_name, value in categories.items():
        name = str(raw_name).strip()
        if not name:
            raise ValidationError("category names must not be empty")
        if name in parsed:
            raise ValidationError(f"duplicate category: {name}")
        parsed[name] = money(value, f"categories.{name}")

    monthly_remaining = money(
        MONTHLY_BUDGET - sum(parsed.values(), Decimal("0")),
        "monthly_remaining",
    )
    week_number = min(((now.day - 1) // 7) + 1, 4)
    cumulative_allowance = money(
        WEEKLY_ALLOWANCE * week_number, "cumulative_allowance"
    )
    cumulative_spent = money(
        sum(
            parsed.get(name, Decimal("0"))
            for name in WEEKLY_SPENDING_CATEGORIES
        ),
        "cumulative_spent",
    )
    weekly_remaining = money(
        cumulative_allowance - cumulative_spent, "weekly_remaining"
    )

    return BudgetResult(
        categories=parsed,
        monthly_remaining=monthly_remaining,
        week_number=week_number,
        cumulative_allowance=cumulative_allowance,
        cumulative_spent=cumulative_spent,
        weekly_remaining=weekly_remaining,
    )


def format_eur(amount: Decimal) -> str:
    absolute = abs(amount).quantize(CENT, rounding=ROUND_HALF_UP)
    prefix = "-€" if amount < 0 else "€"
    return f"{prefix}{absolute:.2f}"


def format_remaining(amount: Decimal) -> str:
    formatted = format_eur(amount)
    return f"{formatted} ⚠️ 已超支" if amount < 0 else formatted


def format_budget_message(
    *,
    total_expense: Decimal,
    total_income: Decimal,
    balance: Decimal,
    result: BudgetResult,
    now: datetime,
) -> str:
    category_lines = "\n".join(
        f"{name}：{format_eur(amount)}"
        for name, amount in result.categories.items()
    )
    return (
        "📊 預算更新\n\n"
        "💰 財務總覽\n"
        f"總支出：{format_eur(total_expense)}\n"
        f"總收入：{format_eur(total_income)}\n"
        f"結餘：{format_eur(balance)}\n\n"
        "🧾 分類支出\n"
        f"{category_lines}\n\n"
        "📅 預算狀態\n"
        f"月預算剩餘：{format_remaining(result.monthly_remaining)}\n"
        f"第 {result.week_number} 週累積額度：{format_eur(result.cumulative_allowance)}\n"
        f"累積已花費（日+食）：{format_eur(result.cumulative_spent)}\n"
        f"週預算剩餘：{format_remaining(result.weekly_remaining)}\n\n"
        f"更新時間：{now:%Y-%m-%d %H:%M}"
    )
