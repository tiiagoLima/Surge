"""Unit tests for ManageMemoryUseCase using FakeMemoryAdapter."""

from src.memory.adapters.outbound.fake_memory_adapter import FakeMemoryAdapter
from src.memory.application.manage_memory_use_case import ManageMemoryUseCase


def test_manage_memory_save_and_retrieve() -> None:
    fake_adapter = FakeMemoryAdapter()
    use_case = ManageMemoryUseCase(memory_storage=fake_adapter)

    entry = use_case.save(
        "Evitar empresas com dívida líquida sobre EBITDA acima de 3x",
        category="risk_rule",
        user_id="user_1",
    )

    assert entry.id
    retrieved = use_case.get(entry.id)
    assert retrieved is not None
    assert retrieved.content == entry.content
    assert retrieved.category == "risk_rule"


def test_manage_memory_search_and_filter() -> None:
    fake_adapter = FakeMemoryAdapter()
    use_case = ManageMemoryUseCase(memory_storage=fake_adapter)

    use_case.save("Gosto de dividendos mensais", category="preference", user_id="user_1")
    use_case.save("Não invisto em empresas de aviação", category="rule", user_id="user_1")
    use_case.save("Gosto de dividendos altos", category="preference", user_id="user_2")

    # Search by keyword for user_1
    res1 = use_case.search("dividendos", user_id="user_1")
    assert len(res1) == 1
    assert res1[0].content == "Gosto de dividendos mensais"

    # Search with category filter
    res2 = use_case.search("dividendos", user_id="user_1", category="rule")
    assert len(res2) == 0

    # User isolation
    res3 = use_case.search("dividendos", user_id="user_2")
    assert len(res3) == 1
    assert res3[0].content == "Gosto de dividendos altos"


def test_manage_memory_list_and_delete() -> None:
    fake_adapter = FakeMemoryAdapter()
    use_case = ManageMemoryUseCase(memory_storage=fake_adapter)

    e1 = use_case.save("Memória A", user_id="user_1")
    use_case.save("Memória B", user_id="user_1")

    all_entries = use_case.list(user_id="user_1")
    assert len(all_entries) == 2

    assert use_case.delete(e1.id) is True
    assert use_case.get(e1.id) is None
    assert len(use_case.list(user_id="user_1")) == 1

    # Delete non-existent
    assert use_case.delete("inexistent-id") is False
