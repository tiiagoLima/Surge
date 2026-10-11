"""Unit tests for finance domain models."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from src.finances.domain.models import (
    CategoryBudget,
    ExpenseCategory,
    Transaction,
    TransactionType,
)


def test_transaction_creation_valid() -> None:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    tx = Transaction(
        id="tx-1",
        amount=50.0,
        category=ExpenseCategory.LEISURE,
        type=TransactionType.EXPENSE,
        description="Cinema",
        created_at=now,
    )
    assert tx.id == "tx-1"
    assert tx.amount == 50.0
    assert tx.category == ExpenseCategory.LEISURE
    assert tx.type == TransactionType.EXPENSE
    assert tx.description == "Cinema"
    assert tx.created_at == now


@pytest.mark.parametrize("invalid_amount", [0.0, -10.0, -0.01])
def test_transaction_invalid_amount_raises_value_error(invalid_amount: float) -> None:
    with pytest.raises(ValueError, match="maior que zero"):
        Transaction(
            id="tx-err",
            amount=invalid_amount,
            category=ExpenseCategory.ESSENTIALS,
            type=TransactionType.EXPENSE,
            description="Invalido",
            created_at=datetime.now(UTC),
        )


def test_transaction_is_immutable() -> None:
    tx = Transaction(
        id="tx-1",
        amount=100.0,
        category=ExpenseCategory.TRANSPORT,
        type=TransactionType.EXPENSE,
        description="Combustivel",
        created_at=datetime.now(UTC),
    )
    with pytest.raises(FrozenInstanceError):
        tx.amount = 120.0  # type: ignore[misc]


def test_category_budget_creation_valid() -> None:
    budget = CategoryBudget(
        category=ExpenseCategory.LEISURE,
        allocated_amount=500.0,
        month="2026-10",
    )
    assert budget.category == ExpenseCategory.LEISURE
    assert budget.allocated_amount == 500.0
    assert budget.month == "2026-10"


@pytest.mark.parametrize("invalid_amount", [0.0, -1.0, -500.0])
def test_category_budget_invalid_amount_raises_value_error(invalid_amount: float) -> None:
    with pytest.raises(ValueError, match="maior que zero"):
        CategoryBudget(
            category=ExpenseCategory.EDUCATION,
            allocated_amount=invalid_amount,
            month="2026-10",
        )


def test_category_budget_remaining_and_usage() -> None:
    budget = CategoryBudget(
        category=ExpenseCategory.ESSENTIALS,
        allocated_amount=400.0,
        month="2026-10",
    )
    assert budget.remaining(spent=100.0) == 300.0
    assert budget.remaining(spent=450.0) == -50.0
    assert budget.usage_pct(spent=200.0) == 50.0
    assert budget.usage_pct(spent=400.0) == 100.0


def test_category_budget_warning_and_exceeded() -> None:
    budget = CategoryBudget(
        category=ExpenseCategory.LEISURE,
        allocated_amount=200.0,
        month="2026-10",
    )
    # 150 / 200 = 75% -> below default 80%
    assert budget.is_warning(spent=150.0) is False
    assert budget.is_exceeded(spent=150.0) is False

    # 160 / 200 = 80% -> warning threshold met
    assert budget.is_warning(spent=160.0) is True
    assert budget.is_exceeded(spent=160.0) is False

    # Custom threshold 70%
    assert budget.is_warning(spent=150.0, threshold_pct=70.0) is True

    # 250 / 200 = 125% -> exceeded
    assert budget.is_warning(spent=250.0) is True
    assert budget.is_exceeded(spent=250.0) is True


def test_category_budget_is_immutable() -> None:
    budget = CategoryBudget(
        category=ExpenseCategory.INVESTMENT,
        allocated_amount=1000.0,
        month="2026-10",
    )
    with pytest.raises(FrozenInstanceError):
        budget.allocated_amount = 1200.0  # type: ignore[misc]
