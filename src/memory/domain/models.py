"""Domain models for the memory bounded context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class MemoryEntry:
    """Represents a persisted user memory, decision, or preference."""

    id: str
    content: str
    category: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        content: str,
        *,
        category: str = "preference",
        user_id: str = "default",
        memory_id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> MemoryEntry:
        """Create a validated memory entry with timestamps and identifier."""
        cleaned_content = str(content).strip()
        if not cleaned_content:
            raise ValueError("O conteúdo da memória não pode ser vazio.")

        cleaned_category = str(category).strip().lower() or "preference"
        cleaned_user_id = str(user_id).strip() or "default"
        now = datetime.now(UTC)

        return cls(
            id=memory_id or str(uuid.uuid4()),
            content=cleaned_content,
            category=cleaned_category,
            user_id=cleaned_user_id,
            created_at=created_at or now,
            updated_at=updated_at or now,
        )

    def summary(self) -> str:
        """Return a concise readable representation."""
        date_str = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"[{self.category.upper()}] {self.content} ({date_str} | id: {self.id})"
