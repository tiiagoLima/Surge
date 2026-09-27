"""Ports for the memory bounded context."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ISemanticMemoryPort(ABC):
    """Stores and retrieves user preferences and historical context."""

    @abstractmethod
    def save_preference(
        self,
        preference: str,
        *,
        user_id: str = "default",
        context: str | None = None,
    ) -> str:
        """Persist a preference and return its identifier."""

    @abstractmethod
    def search_similar_context(
        self,
        query: str,
        *,
        user_id: str = "default",
        limit: int = 10,
    ) -> list[str]:
        """Return preferences matching the query for a user."""
