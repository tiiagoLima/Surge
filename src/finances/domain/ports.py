"""Domain ports (interfaces) for personal finance management."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.finances.domain.models import CategoryBudget, ExpenseCategory, Transaction


class TransactionPort(ABC):
    """Contract for transaction persistence and retrieval."""

    @abstractmethod
    def save(self, transaction: Transaction) -> None:
        """Save a transaction to the data store."""
        pass

    @abstractmethod
    def get_spent_by_category(self, category: ExpenseCategory, month: str) -> float:
        """Retrieve the total amount spent in a specific category for a given month."""
        pass

    @abstractmethod
    def list_by_month(self, month: str) -> list[Transaction]:
        """List all transactions for a specific month."""
        pass


class BudgetPort(ABC):
    """Contract for budget persistence and retrieval."""

    @abstractmethod
    def save_budget(self, budget: CategoryBudget) -> None:
        """Save or update a category budget in the data store."""
        pass

    @abstractmethod
    def get_budget_by_category(
        self, category: ExpenseCategory, month: str
    ) -> CategoryBudget | None:
        """Retrieve the budget for a specific category and month."""
        pass
