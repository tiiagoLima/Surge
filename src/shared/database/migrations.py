"""Small explicit APIs around Alembic migrations and legacy validation."""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

_MEMORY_ANCHORS: dict[str, tuple[Any, Any]] = {}

EXPECTED_SCHEMA: dict[str, set[str]] = {
    "execution_records": {
        "id",
        "capability_id",
        "trigger",
        "req_llm",
        "req_network",
        "req_storage",
        "created_at",
        "started_at",
        "finished_at",
        "status",
        "failure_kind",
        "failure_message",
        "failure_retryable",
        "result_summary",
    },
    "memory_entries": {"id", "user_id", "category", "content", "created_at", "updated_at"},
    "quotes": {"id", "ticker", "price", "currency", "timestamp", "source", "previous_close"},
    "opportunities": {
        "id",
        "ticker",
        "price",
        "currency",
        "timestamp",
        "source",
        "previous_close",
        "drop_pct",
        "threshold_pct",
        "detected_at",
    },
    "holdings": {"ticker", "quantity", "avg_price", "currency", "added_at"},
    "finance_transactions": {
        "id",
        "amount",
        "category",
        "transaction_type",
        "description",
        "created_at",
    },
    "finance_budgets": {"category", "allocated_amount", "month"},
}
EXPECTED_INDEXES = {
    "idx_execution_capability",
    "idx_execution_status",
    "idx_execution_created",
    "idx_memory_user_category",
    "idx_memory_user_created",
    "idx_quotes_ticker_ts",
    "idx_opps_detected",
    "idx_finance_transactions_category_date",
}


def _config(db_path: str | Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(_migrations_path()))
    if isinstance(db_path, str) and db_path == ":memory:":
        raise ValueError("Use create_memory_database for explicit shared in-memory migration")
    path = Path(db_path).expanduser().resolve()
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    return config


def _migrations_path() -> Path:
    """Return the repository's absolute Alembic script directory."""
    return Path(__file__).resolve().parents[3] / "migrations"


def provision_database(db_path: str | Path) -> None:
    """Run migrations to head explicitly for a file-backed database."""
    path = Path(db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(_config(path), "head")


def create_memory_database() -> tuple[str, sqlite3.Connection]:
    """Create and migrate an anchored shared in-memory SQLite database."""
    uri = f"file:surge_migrations_{uuid.uuid4().hex}?mode=memory&cache=shared"
    engine = create_engine(
        "sqlite://",
        creator=lambda: sqlite3.connect(uri, uri=True),
        poolclass=StaticPool,
    )
    with engine.connect() as sqlalchemy_connection:
        config = _config_for_connection()
        config.attributes["connection"] = sqlalchemy_connection
        command.upgrade(config, "head")
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    _MEMORY_ANCHORS[uri] = (engine, connection)
    return uri, connection


def _config_for_connection() -> Config:
    config = Config()
    config.set_main_option("script_location", str(_migrations_path()))
    return config


def introspect_schema(db_path: str | Path) -> dict[str, set[str]]:
    """Return table-to-column names for a SQLite database."""
    with sqlite3.connect(str(Path(db_path).expanduser().resolve())) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {
            table[0]: {row[1] for row in connection.execute(f'PRAGMA table_info("{table[0]}")')}
            for table in tables
        }


def validate_legacy_database(db_path: str | Path) -> dict[str, Any]:
    """Check exact required tables/columns and expected indexes without stamping."""
    actual = introspect_schema(db_path)
    missing_tables = sorted(set(EXPECTED_SCHEMA) - set(actual))
    divergent = {
        table: sorted(EXPECTED_SCHEMA[table] - actual.get(table, set()))
        for table in EXPECTED_SCHEMA
        if table in actual and EXPECTED_SCHEMA[table] - actual[table]
    }
    with sqlite3.connect(str(Path(db_path).expanduser().resolve())) as connection:
        indexes = {
            row[1]
            for row in connection.execute("SELECT type, name FROM sqlite_master WHERE type='index'")
        }
    return {
        "equivalent": not missing_tables and not divergent and indexes >= EXPECTED_INDEXES,
        "missing_tables": missing_tables,
        "divergent_columns": divergent,
        "missing_indexes": sorted(EXPECTED_INDEXES - indexes),
    }


def stamp_legacy_database(db_path: str | Path, *, backup_path: str | Path) -> None:
    """Backup and stamp only an introspectively equivalent legacy database."""
    validation = validate_legacy_database(db_path)
    if not validation["equivalent"]:
        raise ValueError(f"Legacy database is not equivalent: {validation}")
    shutil.copy2(db_path, backup_path)
    config = _config(db_path)
    command.stamp(config, "0001_baseline")
    with sqlite3.connect(str(Path(db_path).expanduser().resolve())) as connection:
        metadata_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_metadata'"
        ).fetchone()
    if metadata_exists is None:
        command.upgrade(config, "head")
    else:
        command.stamp(config, "head")
