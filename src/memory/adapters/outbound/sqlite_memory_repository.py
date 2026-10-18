"""SQLite storage adapter for the memory bounded context."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.memory.domain.models import MemoryEntry
from src.memory.domain.ports import MemoryStoragePort

logger = logging.getLogger(__name__)


class SqliteMemoryRepository(MemoryStoragePort):
    """Persists and retrieves structured memories and preferences using SQLite."""

    def __init__(
        self, db_path: str | Path = "./surge.db", connection: sqlite3.Connection | None = None
    ) -> None:
        """Initialize repository against an explicitly provisioned database."""
        if db_path == ":memory:" and connection is None:
            raise ValueError("Use create_memory_database and pass its connection explicitly")
        self._db_path = Path(db_path).expanduser().resolve()
        self._connection = connection
        self._is_memory = connection is not None

    def _connect(self) -> sqlite3.Connection:
        """Create or return an SQLite connection."""
        if self._connection is not None:
            return self._connection
        if self._is_memory:
            conn = sqlite3.connect(str(self._db_path), uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            return conn
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

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
