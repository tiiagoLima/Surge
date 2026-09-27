"""In-memory semantic memory adapter for local wiring and tests."""

from __future__ import annotations

from uuid import uuid4

from src.domain.ports import ISemanticMemoryPort


class FakeSemanticMemoryAdapter(ISemanticMemoryPort):
    """Stores preferences and performs case-insensitive substring searches."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[str, str, str | None]] = {}

    def save_preference(
        self,
        preference: str,
        *,
        user_id: str = "default",
        context: str | None = None,
    ) -> str:
        memory_id = str(uuid4())
        self._entries[memory_id] = (user_id, preference, context)
        return memory_id

    def search_similar_context(
        self,
        query: str,
        *,
        user_id: str = "default",
        limit: int = 10,
    ) -> list[str]:
        if limit <= 0:
            return []
        normalized_query = query.casefold()
        results: list[str] = []
        for entry_user_id, preference, context in self._entries.values():
            if entry_user_id != user_id:
                continue
            searchable = f"{preference} {context or ''}".casefold()
            if normalized_query in searchable:
                results.append(preference)
                if len(results) >= limit:
                    break
        return results
