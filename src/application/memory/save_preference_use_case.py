"""Use case for saving user preferences."""

from __future__ import annotations

from src.domain.ports import ISemanticMemoryPort


class SavePreferenceUseCase:
    """Saves a preference through the semantic memory port."""

    def __init__(self, memory_port: ISemanticMemoryPort) -> None:
        self._memory = memory_port

    def execute(
        self,
        preference: str,
        *,
        user_id: str = "default",
        context: str | None = None,
    ) -> str:
        """Save a preference and return its identifier."""
        return self._memory.save_preference(
            preference,
            user_id=user_id,
            context=context,
        )
