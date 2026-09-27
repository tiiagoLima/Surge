"""Unit tests for the semantic memory foundation."""

from src.adapters.outbound.fake_semantic_memory import FakeSemanticMemoryAdapter
from src.application.memory.save_preference_use_case import SavePreferenceUseCase
from src.application.memory.search_semantic_memory_use_case import SearchSemanticMemoryUseCase


def test_save_and_search_preference_context() -> None:
    memory = FakeSemanticMemoryAdapter()
    save = SavePreferenceUseCase(memory)
    search = SearchSemanticMemoryUseCase(memory)

    memory_id = save.execute(
        "Não invisto em varejo",
        user_id="user-1",
        context="decisão de carteira",
    )

    assert memory_id
    assert search.execute("varejo", user_id="user-1") == ["Não invisto em varejo"]
    assert search.execute("carteira", user_id="user-1") == ["Não invisto em varejo"]


def test_search_is_case_insensitive_and_respects_user_and_limit() -> None:
    memory = FakeSemanticMemoryAdapter()
    save = SavePreferenceUseCase(memory)
    search = SearchSemanticMemoryUseCase(memory)

    save.execute("Prefiro tecnologia", user_id="user-1")
    save.execute("Não invisto em tecnologia", user_id="user-1")
    save.execute("Invisto em tecnologia", user_id="user-2")

    assert search.execute("TECNOLOGIA", user_id="user-1", limit=1) == ["Prefiro tecnologia"]
    assert search.execute("tecnologia", user_id="user-2") == ["Invisto em tecnologia"]


def test_search_returns_empty_for_no_match_or_non_positive_limit() -> None:
    memory = FakeSemanticMemoryAdapter()
    save = SavePreferenceUseCase(memory)
    search = SearchSemanticMemoryUseCase(memory)

    save.execute("Não invisto em varejo")

    assert search.execute("cripto") == []
    assert search.execute("varejo", limit=0) == []
