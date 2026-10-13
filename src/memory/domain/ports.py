"""Ports for the memory bounded context."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.memory.domain.models import MemoryEntry


class MemoryStoragePort(ABC):
    """Port for persisting and retrieving structured memories, facts, and preferences."""

    @abstractmethod
    def save(self, entry: MemoryEntry) -> None:
        """Persist or update a memory entry."""

    @abstractmethod
    def get_by_id(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a memory entry by its unique identifier."""

    @abstractmethod
    def list_by_user(
        self,
        user_id: str = "default",
        *,
        category: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """List memory entries for a user, optionally filtered by category."""

    @abstractmethod
    def search_text(
        self,
        query: str,
        *,
        user_id: str = "default",
        category: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Perform text matching search across stored memories."""

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Remove a memory entry by identifier. Returns True if deleted."""


class ISemanticMemoryPort(ABC):
    """Port for semantic/vector retrieval (reserved for embeddings in future stages)."""

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
