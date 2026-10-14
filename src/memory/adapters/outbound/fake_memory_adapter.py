"""In-memory fake memory adapter for fast unit testing."""

from __future__ import annotations

from src.memory.domain.models import MemoryEntry
from src.memory.domain.ports import MemoryStoragePort


class FakeMemoryAdapter(MemoryStoragePort):
    """Stores memory entries in a dictionary without I/O."""

    def __init__(self, entries: list[MemoryEntry] | None = None) -> None:
        self._entries: dict[str, MemoryEntry] = {entry.id: entry for entry in (entries or [])}

    def save(self, entry: MemoryEntry) -> None:
        """Persist or update memory in dictionary."""
        self._entries[entry.id] = entry

    def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve memory entry by id."""
        return self._entries.get(str(memory_id).strip())

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
        user_id_clean = str(user_id).strip()
        cat_clean = category.strip().lower() if category else None

        results = [
            e
            for e in self._entries.values()
            if e.user_id == user_id_clean and (cat_clean is None or e.category == cat_clean)
        ]
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def search_text(
        self,
        query: str,
        *,
        user_id: str = "default",
        category: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search entries matching query string case-insensitively."""
        cleaned_query = query.strip().casefold()
        if not cleaned_query or limit <= 0:
            return []

        user_id_clean = str(user_id).strip()
        cat_clean = category.strip().lower() if category else None

        matches = [
            e
            for e in self._entries.values()
            if e.user_id == user_id_clean
            and (cat_clean is None or e.category == cat_clean)
            and cleaned_query in e.content.casefold()
        ]
        matches.sort(key=lambda e: e.created_at, reverse=True)
        return matches[:limit]

    def delete(self, memory_id: str) -> bool:
        """Delete an entry by id or prefix (min 6 chars)."""
        clean_id = str(memory_id).strip()
        if not clean_id:
            return False
        if clean_id in self._entries:
            del self._entries[clean_id]
            return True
        if len(clean_id) >= 6:
            matching = [k for k in self._entries if k.startswith(clean_id)]
            if matching:
                for k in matching:
                    del self._entries[k]
                return True
        return False
