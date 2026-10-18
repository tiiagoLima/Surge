"""Baseline schema matching the four existing SQLite repositories."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_records",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("capability_id", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("req_llm", sa.Text(), nullable=False),
        sa.Column("req_network", sa.Text(), nullable=False),
        sa.Column("req_storage", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text()),
        sa.Column("finished_at", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_kind", sa.Text()),
        sa.Column("failure_message", sa.Text()),
        sa.Column("failure_retryable", sa.Integer()),
        sa.Column("result_summary", sa.Text(), nullable=False),
    )
    op.create_index("idx_execution_capability", "execution_records", ["capability_id"])
    op.create_index("idx_execution_status", "execution_records", ["status"])
    op.create_index("idx_execution_created", "execution_records", ["created_at"])
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_memory_user_category", "memory_entries", ["user_id", "category"])
    op.create_index("idx_memory_user_created", "memory_entries", ["user_id", "created_at"])
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("previous_close", sa.Float()),
    )
    op.create_index("idx_quotes_ticker_ts", "quotes", ["ticker", sa.text("timestamp DESC")])
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("previous_close", sa.Float()),
        sa.Column("drop_pct", sa.Float(), nullable=False),
        sa.Column("threshold_pct", sa.Float(), nullable=False),
        sa.Column("detected_at", sa.Text(), nullable=False),
    )
    op.execute("CREATE INDEX idx_opps_detected ON opportunities(detected_at DESC)")
    op.create_table(
        "holdings",
        sa.Column("ticker", sa.Text(), primary_key=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float()),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("added_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "finance_transactions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_finance_transactions_category_date",
        "finance_transactions",
        ["category", "created_at"],
    )
    op.create_table(
        "finance_budgets",
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("allocated_amount", sa.Float(), nullable=False),
        sa.Column("month", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("category", "month"),
    )


def downgrade() -> None:
    for index_name, table_name in (
        ("idx_finance_transactions_category_date", "finance_transactions"),
        ("idx_opps_detected", "opportunities"),
        ("idx_quotes_ticker_ts", "quotes"),
        ("idx_memory_user_created", "memory_entries"),
        ("idx_memory_user_category", "memory_entries"),
        ("idx_execution_created", "execution_records"),
        ("idx_execution_status", "execution_records"),
        ("idx_execution_capability", "execution_records"),
    ):
        op.drop_index(index_name, table_name=table_name)
    for table_name in (
        "finance_budgets",
        "finance_transactions",
        "holdings",
        "opportunities",
        "quotes",
        "memory_entries",
        "execution_records",
    ):
        op.drop_table(table_name)
