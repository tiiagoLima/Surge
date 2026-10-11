"""Application use cases for setting budgets and generating monthly summaries."""

from __future__ import annotations

from dataclasses import dataclass

from src.finances.domain.models import CategoryBudget, ExpenseCategory
from src.finances.domain.ports import BudgetPort, TransactionPort


@dataclass(frozen=True)
class CategorySummary:
    """Summary of spending and budget status for a category."""

    category: ExpenseCategory
    spent: float
    budget: CategoryBudget | None

    @property
    def allocated(self) -> float | None:
        """Return the allocated budget amount if defined."""
        return self.budget.allocated_amount if self.budget is not None else None

    @property
    def remaining(self) -> float | None:
        """Return remaining budget amount if defined."""
        if self.budget is None:
            return None
        return self.budget.remaining(self.spent)

    @property
    def usage_pct(self) -> float | None:
        """Return usage percentage if defined."""
        if self.budget is None:
            return None
        return self.budget.usage_pct(self.spent)

    @property
    def is_warning(self) -> bool:
        """Return True if spending has reached warning threshold."""
        if self.budget is None:
            return False
        return self.budget.is_warning(self.spent)

    @property
    def is_exceeded(self) -> bool:
        """Return True if spending exceeded the budget."""
        if self.budget is None:
            return False
        return self.budget.is_exceeded(self.spent)


@dataclass(frozen=True)
class MonthlySummary:
    """Aggregated monthly financial summary."""

    month: str
    categories: list[CategorySummary]
    total_spent: float


class SetBudgetUseCase:
    """Set or update a monthly category budget."""

    def __init__(self, budget_port: BudgetPort) -> None:
        """Initialize use case with budget port."""
        self._budget_port = budget_port

    def execute(self, category: ExpenseCategory, amount: float, month: str) -> CategoryBudget:
        """Persist a category budget for the given month."""
        budget = CategoryBudget(category=category, allocated_amount=amount, month=month)
        self._budget_port.save_budget(budget)
        return budget


class GetMonthlySummaryUseCase:
    """Compile a monthly spending and budget summary."""

    def __init__(self, transaction_port: TransactionPort, budget_port: BudgetPort) -> None:
        """Initialize use case with transaction and budget ports."""
        self._transaction_port = transaction_port
        self._budget_port = budget_port

    def execute(self, month: str) -> MonthlySummary:
        """Build summary for all categories in the specified month."""
        categories_summary: list[CategorySummary] = []
        total_spent = 0.0

        for category in ExpenseCategory:
            spent = self._transaction_port.get_spent_by_category(category, month)
            budget = self._budget_port.get_budget_by_category(category, month)
            total_spent += spent
            categories_summary.append(
                CategorySummary(
                    category=category,
                    spent=spent,
                    budget=budget,
                )
            )

        return MonthlySummary(
            month=month,
            categories=categories_summary,
            total_spent=total_spent,
        )
