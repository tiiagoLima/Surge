"""Domain models for personal finance management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ExpenseCategory(Enum):
    """Categories for expense tracking and budgeting."""

    ESSENTIALS = "Essenciais"
    LEISURE = "Lazer"
    EDUCATION = "Educação"
    TRANSPORT = "Transporte"
    FOOD = "Alimentação"
    INVESTMENT = "Investimento"
    HEALTH = "Saúde"


class TransactionType(Enum):
    """Type of transaction."""

    INCOME = "Entrada"
    EXPENSE = "Saída"


@dataclass(frozen=True)
class Transaction:
    """Represents a financial transaction.

    Attributes:
        id: Unique identifier.
        amount: Transaction value (strictly greater than zero).
        category: Associated expense or allocation category.
        type: Direction of transaction (income or expense).
        description: Note or title of the transaction.
        created_at: Date and time when transaction was created.
    """

    id: str
    amount: float
    category: ExpenseCategory
    type: TransactionType
    description: str
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate invariant business rules."""
        if self.amount <= 0:
            raise ValueError(
                f"Operação inválida. O valor da transação deve "
                f"ser maior que zero, mas recebi {self.amount}"
            )


@dataclass(frozen=True)
class CategoryBudget:
    """Monthly budget set for a specific category.

    Attributes:
        category: Category associated with this limit.
        allocated_amount: Total planned amount for the month (> 0).
        month: Reference month in 'YYYY-MM' format.
    """

    category: ExpenseCategory
    allocated_amount: float
    month: str

    def __post_init__(self) -> None:
        """Validate the budget constraint."""
        if self.allocated_amount <= 0:
            raise ValueError(
                f"O teto do orçamento deve ser maior que zero, mas recebi {self.allocated_amount}"
            )

    def remaining(self, spent: float) -> float:
        """Calculate the remaining amount available."""
        return self.allocated_amount - spent

    def usage_pct(self, spent: float) -> float:
        """Calculate percentage of allocation consumed."""
        return (spent / self.allocated_amount) * 100

    def is_warning(self, spent: float, threshold_pct: float = 80.0) -> bool:
        """Check if consumption has reached the defined alert zone."""
        return self.usage_pct(spent) >= threshold_pct

    def is_exceeded(self, spent: float) -> bool:
        """Check whether the budget limit has been breached."""
        return spent > self.allocated_amount
