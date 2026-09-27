"""Use case for searching semantic memory."""

from __future__ import annotations

from src.domain.ports import ISemanticMemoryPort


class SearchSemanticMemoryUseCase:
    """Searches historical user context through the semantic memory port."""

    def __init__(self, memory_port: ISemanticMemoryPort) -> None:
        self._memory = memory_port

    def execute(
        self,
        query: str,
        *,
        user_id: str = "default",
        limit: int = 10,
    ) -> list[str]:
        """Return matching preferences and context."""
        return self._memory.search_similar_context(
            query,
            user_id=user_id,
            limit=limit,
        )
