"""Unit tests for memory domain models."""

import pytest

from src.memory.domain.models import MemoryEntry


def test_memory_entry_creation_defaults() -> None:
    entry = MemoryEntry.create("Prefiro empresas boas pagadoras de dividendos")
    assert entry.id
    assert entry.content == "Prefiro empresas boas pagadoras de dividendos"
    assert entry.category == "preference"
    assert entry.user_id == "default"
    assert entry.created_at is not None
    assert entry.updated_at is not None
    assert "DIVIDENDOS" in entry.summary().upper()


def test_memory_entry_validation_empty_content_raises() -> None:
    with pytest.raises(ValueError, match="não pode ser vazio"):
        MemoryEntry.create("   ")


def test_memory_entry_custom_attributes() -> None:
    entry = MemoryEntry.create(
        "Alvo de alocação: 30% em FIIs",
        category="target_allocation",
        user_id="user_abc",
        memory_id="fixed-uuid",
    )
    assert entry.id == "fixed-uuid"
    assert entry.category == "target_allocation"
    assert entry.user_id == "user_abc"
    assert "TARGET_ALLOCATION" in entry.summary()
