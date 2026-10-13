"""SQLite storage adapter for the memory bounded context."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from src.memory.domain.models import MemoryEntry
from src.memory.domain.ports import MemoryStoragePort

logger = logging.getLogger(__name__)


class SqliteMemoryRepository(MemoryStoragePort):
    """Persists and retrieves structured memories and preferences using SQLite."""

    def __init__(self, db_path: str | Path = "./surge.db") -> None:
        """Initialize repository with target SQLite file path or in-memory database."""
        self._memory_conn: sqlite3.Connection | None = None
        if isinstance(db_path, str) and db_path == ":memory:":
            mem_id = uuid.uuid4().hex
            self._db_path: str | Path = f"file:mem_memory_{mem_id}?mode=memory&cache=shared"
            self._is_memory = True
            self._memory_conn = sqlite3.connect(str(self._db_path), uri=True, timeout=10)
            self._memory_conn.row_factory = sqlite3.Row
        else:
            self._db_path = Path(db_path).expanduser().resolve()
            self._is_memory = False
            self._memory_conn = None
            try:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                self._db_path = Path("/tmp") / self._db_path.name
                self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Create or return an SQLite connection."""
        if self._is_memory:
            conn = sqlite3.connect(str(self._db_path), uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            return conn
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create memory table and indexes idempotently."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_user_category
                    ON memory_entries(user_id, category);
                CREATE INDEX IF NOT EXISTS idx_memory_user_created
                    ON memory_entries(user_id, created_at);
            """)

    def save(self, entry: MemoryEntry) -> None:
        """Persist or update a memory entry in SQLite."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_entries (id, user_id, category, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id=excluded.user_id,
                    category=excluded.category,
                    content=excluded.content,
                    updated_at=excluded.updated_at
                """,
                (
                    entry.id,
                    entry.user_id,
                    entry.category,
                    entry.content,
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ),
            )

    def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a memory entry by unique identifier."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, category, content, created_at, updated_at
                FROM memory_entries
                WHERE id = ?
                """,
                (str(memory_id).strip(),),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_entry(row)

    def list_by_user(
        self,
        user_id: str = "default",
        *,
        category: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """List memory entries for a user, optionally filtered by category."""
        if limit <= 0:
            return []

        query = """
            SELECT id, user_id, category, content, created_at, updated_at
            FROM memory_entries
            WHERE user_id = ?
        """
        params: list[object] = [str(user_id).strip()]

        if category is not None and category.strip():
            query += " AND category = ?"
            params.append(category.strip().lower())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def search_text(
        self,
        query: str,
        *,
        user_id: str = "default",
        category: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Perform text matching search across stored memories."""
        cleaned_query = query.strip()
        if not cleaned_query or limit <= 0:
            return []

        sql = """
            SELECT id, user_id, category, content, created_at, updated_at
            FROM memory_entries
            WHERE user_id = ?
              AND LOWER(content) LIKE LOWER(?)
        """
        params: list[object] = [str(user_id).strip(), f"%{cleaned_query}%"]

        if category is not None and category.strip():
            sql += " AND category = ?"
            params.append(category.strip().lower())

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        """Remove a memory entry by identifier or prefix (min 6 chars). Returns True if deleted."""
        clean_id = str(memory_id).strip()
        if not clean_id:
            return False

        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM memory_entries
                WHERE id = ? OR (length(?) >= 6 AND id LIKE ?)
                """,
                (clean_id, clean_id, f"{clean_id}%"),
            )
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        """Convert an SQLite row to a MemoryEntry domain object."""
        return MemoryEntry(
            id=row["id"],
            user_id=row["user_id"],
            category=row["category"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
