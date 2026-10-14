"""Use case for saving user preferences."""

from __future__ import annotations

from src.memory.domain.models import MemoryEntry
from src.memory.domain.ports import ISemanticMemoryPort, MemoryStoragePort


class SavePreferenceUseCase:
    """Saves a preference through the memory storage port."""

    def __init__(self, memory_port: MemoryStoragePort | ISemanticMemoryPort) -> None:
        self._memory = memory_port

    def execute(
        self,
        preference: str,
        *,
        user_id: str = "default",
        context: str | None = None,
    ) -> str:
        """Save a preference and return its identifier."""
        if isinstance(self._memory, MemoryStoragePort):
            content = f"{preference} (context: {context})" if context else preference
            entry = MemoryEntry.create(
                content=content,
                category="preference",
                user_id=user_id,
            )
            self._memory.save(entry)
            return entry.id

        return self._memory.save_preference(
            preference,
            user_id=user_id,
            context=context,
        )
