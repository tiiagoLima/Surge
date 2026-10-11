"""Unit tests for finance application use cases."""

from src.finances.application.register_expense_use_case import RegisterExpenseUseCase
from src.finances.domain.models import CategoryBudget, ExpenseCategory, Transaction
from src.finances.domain.ports import BudgetPort, TransactionPort


class FakeTransactionPort(TransactionPort):
    def __init__(self, total_spent: float) -> None:
        self.total_spent = total_spent
        self.saved: list[Transaction] = []

    def save(self, transaction: Transaction) -> None:
        self.saved.append(transaction)

    def get_spent_by_category(self, category: ExpenseCategory, month: str) -> float:
        return self.total_spent

    def list_by_month(self, month: str) -> list[Transaction]:
        return self.saved


class FakeBudgetPort(BudgetPort):
    def __init__(self, budget: CategoryBudget | None) -> None:
        self.budget = budget

    def save_budget(self, budget: CategoryBudget) -> None:
        self.budget = budget

    def get_budget_by_category(
        self, category: ExpenseCategory, month: str
    ) -> CategoryBudget | None:
        return self.budget


def test_register_expense_returns_budget_status() -> None:
    transaction_port = FakeTransactionPort(total_spent=400.0)
    budget_port = FakeBudgetPort(CategoryBudget(ExpenseCategory.LEISURE, 500.0, "2026-10"))
    use_case = RegisterExpenseUseCase(transaction_port, budget_port)

    result = use_case.execute(50.0, ExpenseCategory.LEISURE, "Cinema", "2026-10")

    assert len(transaction_port.saved) == 1
    assert result.transaction.amount == 50.0
    assert result.total_spent == 400.0
    assert result.remaining == 100.0
    assert result.usage_pct == 80.0
    assert result.warning is True
    assert result.exceeded is False


def test_register_expense_without_budget_returns_unbounded_status() -> None:
    transaction_port = FakeTransactionPort(total_spent=50.0)
    use_case = RegisterExpenseUseCase(transaction_port, FakeBudgetPort(None))

    result = use_case.execute(50.0, ExpenseCategory.HEALTH, "Consulta", "2026-10")

    assert result.remaining is None
    assert result.usage_pct is None
    assert result.warning is False
    assert result.exceeded is False
