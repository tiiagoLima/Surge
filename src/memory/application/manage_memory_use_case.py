"""Application use case for managing structured memories, facts, and preferences."""

from __future__ import annotations

import builtins

from src.memory.domain.models import MemoryEntry
from src.memory.domain.ports import MemoryStoragePort


class ManageMemoryUseCase:
    """Orchestrates creation, search, listing, and deletion of user memories."""

    def __init__(self, memory_storage: MemoryStoragePort) -> None:
        """Initialize use case with storage port."""
        self._storage = memory_storage

    def save(
        self,
        content: str,
        *,
        category: str = "preference",
        user_id: str = "default",
        memory_id: str | None = None,
    ) -> MemoryEntry:
        """Create and persist a new or updated memory entry."""
        entry = MemoryEntry.create(
            content=content,
            category=category,
            user_id=user_id,
            memory_id=memory_id,
        )
        self._storage.save(entry)
        return entry

    def list(
        self,
        *,
        user_id: str = "default",
        category: str | None = None,
        limit: int = 100,
    ) -> builtins.list[MemoryEntry]:
        """List memory entries for a user."""
        return self._storage.list_by_user(user_id=user_id, category=category, limit=limit)

    def search(
        self,
        query: str,
        *,
        user_id: str = "default",
        category: str | None = None,
        limit: int = 10,
    ) -> builtins.list[MemoryEntry]:
        """Search memory entries by text."""
        return self._storage.search_text(
            query=query,
            user_id=user_id,
            category=category,
            limit=limit,
        )

    def get(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a specific memory by identifier."""
        return self._storage.get_by_id(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Remove a memory by identifier."""
        return self._storage.delete(memory_id)
