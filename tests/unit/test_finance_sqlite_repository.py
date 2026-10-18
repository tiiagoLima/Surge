"""Unit tests for the finance SQLite adapter."""

from datetime import UTC, datetime

from src.finances.adapters.outbound.sqlite_repository import FinanceSqliteRepository
from src.finances.domain.models import CategoryBudget, ExpenseCategory, Transaction, TransactionType
from src.shared.database.migrations import create_memory_database


def _repository() -> FinanceSqliteRepository:
    _, connection = create_memory_database()
    return FinanceSqliteRepository(":memory:", connection=connection)


def test_repository_persists_transactions_and_calculates_monthly_spending() -> None:
    repository = _repository()
    repository.save(
        Transaction(
            id="expense-1",
            amount=120.0,
            category=ExpenseCategory.FOOD,
            type=TransactionType.EXPENSE,
            description="Mercado",
            created_at=datetime(2026, 10, 5, tzinfo=UTC),
        )
    )
    repository.save(
        Transaction(
            id="income-1",
            amount=2000.0,
            category=ExpenseCategory.ESSENTIALS,
            type=TransactionType.INCOME,
            description="Salário",
            created_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
    )

    assert repository.get_spent_by_category(ExpenseCategory.FOOD, "2026-10") == 120.0
    assert repository.get_spent_by_category(ExpenseCategory.FOOD, "2026-11") == 0.0
    transactions = repository.list_by_month("2026-10")
    assert [transaction.id for transaction in transactions] == ["income-1", "expense-1"]


def test_repository_persists_and_retrieves_budget() -> None:
    repository = _repository()
    budget = CategoryBudget(ExpenseCategory.LEISURE, 500.0, "2026-10")

    repository.save_budget(budget)

    assert repository.get_budget_by_category(ExpenseCategory.LEISURE, "2026-10") == budget
    assert repository.get_budget_by_category(ExpenseCategory.LEISURE, "2026-11") is None
