"""SQLite adapter for the finance bounded context."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from src.finances.domain.models import (
    CategoryBudget,
    ExpenseCategory,
    Transaction,
    TransactionType,
)
from src.finances.domain.ports import BudgetPort, TransactionPort


class FinanceSqliteRepository(TransactionPort, BudgetPort):
    """Persist finance transactions and budgets in SQLite."""

    def __init__(
        self, db_path: str | Path = "./surge.db", connection: sqlite3.Connection | None = None
    ) -> None:
        """Initialize a repository against an explicitly provisioned database."""
        if db_path == ":memory:" and connection is None:
            raise ValueError("Use create_memory_database and pass its connection explicitly")
        self._db_path = str(db_path)
        self._memory_connection = connection

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with rows accessible by column name."""
        if self._memory_connection is not None:
            return self._memory_connection
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def save(self, transaction: Transaction) -> None:
        """Persist a transaction."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO finance_transactions
                    (id, amount, category, transaction_type, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.id,
                    transaction.amount,
                    transaction.category.value,
                    transaction.type.value,
                    transaction.description,
                    transaction.created_at.isoformat(),
                ),
            )

    def get_spent_by_category(self, category: ExpenseCategory, month: str) -> float:
        """Return expenses for a category within a calendar month."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM finance_transactions
                WHERE category = ?
                  AND transaction_type = ?
                  AND substr(created_at, 1, 7) = ?
                """,
                (category.value, TransactionType.EXPENSE.value, month),
            ).fetchone()
        return float(row["total"])

    def list_by_month(self, month: str) -> list[Transaction]:
        """List all transactions within a calendar month."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM finance_transactions
                WHERE substr(created_at, 1, 7) = ?
                ORDER BY created_at
                """,
                (month,),
            ).fetchall()
        return [self._to_transaction(row) for row in rows]

    def save_budget(self, budget: CategoryBudget) -> None:
        """Persist or replace a category budget for a month."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO finance_budgets
                    (category, allocated_amount, month)
                VALUES (?, ?, ?)
                """,
                (budget.category.value, budget.allocated_amount, budget.month),
            )

    def get_budget_by_category(
        self, category: ExpenseCategory, month: str
    ) -> CategoryBudget | None:
        """Retrieve a category budget for a month."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT category, allocated_amount, month
                FROM finance_budgets
                WHERE category = ? AND month = ?
                """,
                (category.value, month),
            ).fetchone()
        if row is None:
            return None
        return CategoryBudget(
            category=ExpenseCategory(row["category"]),
            allocated_amount=float(row["allocated_amount"]),
            month=row["month"],
        )

    @staticmethod
    def _to_transaction(row: sqlite3.Row) -> Transaction:
        """Convert a database row into a domain transaction."""
        return Transaction(
            id=row["id"],
            amount=float(row["amount"]),
            category=ExpenseCategory(row["category"]),
            type=TransactionType(row["transaction_type"]),
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
