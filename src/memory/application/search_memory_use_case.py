"""Use case for searching structured memory entries."""

from __future__ import annotations

from src.memory.domain.models import MemoryEntry
from src.memory.domain.ports import MemoryStoragePort


class SearchMemoryUseCase:
    """Searches stored memory entries by text and optional category."""

    def __init__(self, storage_port: MemoryStoragePort) -> None:
        self._storage = storage_port

    def execute(
        self,
        query: str,
        *,
        user_id: str = "default",
        category: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Return matching memory entries."""
        return self._storage.search_text(
            query=query,
            user_id=user_id,
            category=category,
            limit=limit,
        )
