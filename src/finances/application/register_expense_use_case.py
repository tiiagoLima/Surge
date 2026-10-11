""" ""Application use case for registering finance expenses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.finances.domain.models import ExpenseCategory, Transaction, TransactionType
from src.finances.domain.ports import BudgetPort, TransactionPort


@dataclass(frozen=True)
class ExpenseRegistrationResult:
    """Result of registering an expense and evaluating its budget."""

    transaction: Transaction
    total_spent: float
    remaining: float | None
    usage_pct: float | None
    warning: bool
    exceeded: bool


class RegisterExpenseUseCase:
    """Register an expense and evaluate the matching monthly budget."""

    def __init__(self, transaction_port: TransactionPort, budget_port: BudgetPort) -> None:
        """Initialize the use case with persistence ports."""
        self._transaction_port = transaction_port
        self._budget_port = budget_port

    def execute(
        self,
        amount: float,
        category: ExpenseCategory,
        description: str,
        month: str,
    ) -> ExpenseRegistrationResult:
        """Save an expense and return its current budget status."""
        transaction = Transaction(
            id=str(uuid.uuid4()),
            amount=amount,
            category=category,
            type=TransactionType.EXPENSE,
            description=description,
            created_at=datetime.now(UTC),
        )
        self._transaction_port.save(transaction)
        total_spent = self._transaction_port.get_spent_by_category(category, month)
        budget = self._budget_port.get_budget_by_category(category, month)

        if budget is None:
            return ExpenseRegistrationResult(
                transaction=transaction,
                total_spent=total_spent,
                remaining=None,
                usage_pct=None,
                warning=False,
                exceeded=False,
            )

        return ExpenseRegistrationResult(
            transaction=transaction,
            total_spent=total_spent,
            remaining=budget.remaining(total_spent),
            usage_pct=budget.usage_pct(total_spent),
            warning=budget.is_warning(total_spent),
            exceeded=budget.is_exceeded(total_spent),
        )
