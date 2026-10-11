"""Unit tests for budget management and monthly summary use cases."""

from src.finances.application.manage_budget_use_case import (
    GetMonthlySummaryUseCase,
    SetBudgetUseCase,
)
from src.finances.domain.models import CategoryBudget, ExpenseCategory, Transaction
from src.finances.domain.ports import BudgetPort, TransactionPort


class FakeTransactionPort(TransactionPort):
    def __init__(self, spending_map: dict[ExpenseCategory, float] | None = None) -> None:
        self.spending_map = spending_map or {}
        self.transactions: list[Transaction] = []

    def save(self, transaction: Transaction) -> None:
        self.transactions.append(transaction)

    def get_spent_by_category(self, category: ExpenseCategory, month: str) -> float:
        return self.spending_map.get(category, 0.0)

    def list_by_month(self, month: str) -> list[Transaction]:
        return self.transactions


class FakeBudgetPort(BudgetPort):
    def __init__(
        self, budgets: dict[tuple[ExpenseCategory, str], CategoryBudget] | None = None
    ) -> None:
        self.budgets = budgets or {}

    def save_budget(self, budget: CategoryBudget) -> None:
        self.budgets[(budget.category, budget.month)] = budget

    def get_budget_by_category(
        self, category: ExpenseCategory, month: str
    ) -> CategoryBudget | None:
        return self.budgets.get((category, month))


def test_set_budget_persists_and_returns_budget() -> None:
    budget_port = FakeBudgetPort()
    use_case = SetBudgetUseCase(budget_port=budget_port)

    budget = use_case.execute(
        category=ExpenseCategory.LEISURE,
        amount=450.0,
        month="2026-10",
    )

    assert budget.category == ExpenseCategory.LEISURE
    assert budget.allocated_amount == 450.0
    assert budget.month == "2026-10"
    assert budget_port.get_budget_by_category(ExpenseCategory.LEISURE, "2026-10") == budget


def test_get_monthly_summary_aggregates_totals_and_status() -> None:
    transaction_port = FakeTransactionPort(
        spending_map={
            ExpenseCategory.FOOD: 600.0,
            ExpenseCategory.LEISURE: 350.0,
            ExpenseCategory.TRANSPORT: 100.0,
        }
    )
    budget_port = FakeBudgetPort(
        budgets={
            (ExpenseCategory.FOOD, "2026-10"): CategoryBudget(
                ExpenseCategory.FOOD, 800.0, "2026-10"
            ),
            (ExpenseCategory.LEISURE, "2026-10"): CategoryBudget(
                ExpenseCategory.LEISURE, 400.0, "2026-10"
            ),
        }
    )

    use_case = GetMonthlySummaryUseCase(
        transaction_port=transaction_port,
        budget_port=budget_port,
    )
    summary = use_case.execute(month="2026-10")

    assert summary.month == "2026-10"
    assert summary.total_spent == 1050.0

    food_item = next(c for c in summary.categories if c.category == ExpenseCategory.FOOD)
    assert food_item.spent == 600.0
    assert food_item.allocated == 800.0
    assert food_item.remaining == 200.0
    assert food_item.usage_pct == 75.0
    assert food_item.is_warning is False
    assert food_item.is_exceeded is False

    leisure_item = next(c for c in summary.categories if c.category == ExpenseCategory.LEISURE)
    assert leisure_item.spent == 350.0
    assert leisure_item.allocated == 400.0
    assert leisure_item.remaining == 50.0
    assert leisure_item.usage_pct == 87.5
    assert leisure_item.is_warning is True
    assert leisure_item.is_exceeded is False

    transport_item = next(c for c in summary.categories if c.category == ExpenseCategory.TRANSPORT)
    assert transport_item.spent == 100.0
    assert transport_item.allocated is None
    assert transport_item.remaining is None
    assert transport_item.usage_pct is None
    assert transport_item.is_warning is False
    assert transport_item.is_exceeded is False
