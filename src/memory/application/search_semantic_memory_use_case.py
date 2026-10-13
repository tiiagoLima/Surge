"""Use case for searching memory."""

from __future__ import annotations

from src.memory.domain.ports import ISemanticMemoryPort, MemoryStoragePort


class SearchSemanticMemoryUseCase:
    """Searches historical user context through the memory port."""

    def __init__(self, memory_port: MemoryStoragePort | ISemanticMemoryPort) -> None:
        self._memory = memory_port

    def execute(
        self,
        query: str,
        *,
        user_id: str = "default",
        limit: int = 10,
    ) -> list[str]:
        """Return matching preferences and context."""
        if isinstance(self._memory, MemoryStoragePort):
            entries = self._memory.search_text(
                query=query,
                user_id=user_id,
                limit=limit,
            )
            return [e.content for e in entries]

        return self._memory.search_similar_context(
            query,
            user_id=user_id,
            limit=limit,
        )
