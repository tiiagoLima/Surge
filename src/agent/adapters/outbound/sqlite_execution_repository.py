"""SQLite adapter for execution lifecycle records."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from src.agent.domain.capabilities import CapabilityRequirements, RequirementLevel
from src.agent.domain.executions import ExecutionRecord, ExecutionStatus
from src.agent.domain.ports import ExecutionRecordPort
from src.agent.domain.provider_health import ProviderFailure, ProviderFailureKind


class SqliteExecutionRepository(ExecutionRecordPort):
    """Persist immutable execution snapshots with idempotent SQLite DDL."""

    def __init__(self, db_path: str | Path = "./surge.db") -> None:
        self._memory_conn: sqlite3.Connection | None = None
        if isinstance(db_path, str) and db_path == ":memory:":
            self._db_path: str | Path = (
                f"file:mem_execution_{uuid.uuid4().hex}?mode=memory&cache=shared"
            )
            self._is_memory = True
            self._memory_conn = self._connect()
        else:
            self._db_path = Path(db_path).expanduser().resolve()
            self._is_memory = False
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._is_memory:
            conn = sqlite3.connect(str(self._db_path), uri=True, timeout=10)
        else:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS execution_records (
                    id TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    req_llm TEXT NOT NULL,
                    req_network TEXT NOT NULL,
                    req_storage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    failure_kind TEXT,
                    failure_message TEXT,
                    failure_retryable INTEGER,
                    result_summary TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_execution_capability
                    ON execution_records(capability_id);
                CREATE INDEX IF NOT EXISTS idx_execution_status
                    ON execution_records(status);
                CREATE INDEX IF NOT EXISTS idx_execution_created
                    ON execution_records(created_at);
                """)

    def save(self, record: ExecutionRecord) -> None:
        """Upsert a validated execution record."""
        failure = record.failure
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO execution_records (
                    id, capability_id, trigger, req_llm, req_network, req_storage,
                    created_at, started_at, finished_at, status,
                    failure_kind, failure_message, failure_retryable, result_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    capability_id=excluded.capability_id, trigger=excluded.trigger,
                    req_llm=excluded.req_llm, req_network=excluded.req_network,
                    req_storage=excluded.req_storage, created_at=excluded.created_at,
                    started_at=excluded.started_at, finished_at=excluded.finished_at,
                    status=excluded.status, failure_kind=excluded.failure_kind,
                    failure_message=excluded.failure_message,
                    failure_retryable=excluded.failure_retryable,
                    result_summary=excluded.result_summary
                """,
                (
                    record.id,
                    record.capability_id,
                    record.trigger,
                    record.requirements.llm.value,
                    record.requirements.network.value,
                    record.requirements.storage.value,
                    record.created_at.isoformat(),
                    record.started_at.isoformat() if record.started_at else None,
                    record.finished_at.isoformat() if record.finished_at else None,
                    record.status.value,
                    failure.kind.value if failure else None,
                    failure.message if failure else None,
                    int(failure.retryable) if failure else None,
                    record.result_summary,
                ),
            )

    def get_by_id(self, execution_id: str) -> ExecutionRecord | None:
        """Rehydrate and revalidate one execution record."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution_records WHERE id = ?", (str(execution_id).strip(),)
            ).fetchone()
        return self._row_to_record(row) if row else None

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ExecutionRecord:
        failure = None
        if row["failure_kind"] is not None:
            failure = ProviderFailure(
                ProviderFailureKind(row["failure_kind"]),
                row["failure_message"],
                bool(row["failure_retryable"]),
            )
        return ExecutionRecord(
            id=row["id"],
            capability_id=row["capability_id"],
            trigger=row["trigger"],
            requirements=CapabilityRequirements(
                llm=RequirementLevel(row["req_llm"]),
                network=RequirementLevel(row["req_network"]),
                storage=RequirementLevel(row["req_storage"]),
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            status=ExecutionStatus(row["status"]),
            failure=failure,
            result_summary=row["result_summary"],
        )
