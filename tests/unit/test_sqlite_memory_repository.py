"""Unit and integration tests for SqliteMemoryRepository."""

from pathlib import Path

from src.memory.adapters.outbound.sqlite_memory_repository import SqliteMemoryRepository
from src.memory.domain.models import MemoryEntry


def test_sqlite_memory_repository_in_memory_crud() -> None:
    repo = SqliteMemoryRepository(db_path=":memory:")

    entry = MemoryEntry.create(
        "Prefiro setores perenes como energia elétrica e saneamento",
        category="strategy",
        user_id="tiago",
    )
    repo.save(entry)

    # Retrieval by id
    fetched = repo.get_by_id(entry.id)
    assert fetched is not None
    assert fetched.content == entry.content
    assert fetched.category == "strategy"
    assert fetched.user_id == "tiago"

    # Search text
    results = repo.search_text("energia", user_id="tiago")
    assert len(results) == 1
    assert results[0].id == entry.id

    # List entries
    listed = repo.list_by_user("tiago")
    assert len(listed) == 1

    # Delete
    assert repo.delete(entry.id) is True
    assert repo.get_by_id(entry.id) is None
    assert repo.delete("not-found") is False


def test_sqlite_memory_repository_persists_across_restarts(tmp_path: Path) -> None:
    db_file = tmp_path / "test_persistence.db"

    # Session 1: save memories and simulate process exit
    repo_session_1 = SqliteMemoryRepository(db_path=db_file)
    e1 = MemoryEntry.create(
        "Foco em valuation pelo método de Graham",
        category="valuation",
        user_id="default",
    )
    e2 = MemoryEntry.create(
        "Reserva de emergência deve ser mantida em Selic ou CDI 100%",
        category="rule",
        user_id="default",
    )
    repo_session_1.save(e1)
    repo_session_1.save(e2)
    del repo_session_1

    # Session 2: open new repository instance on same file path (simulates restart)
    repo_session_2 = SqliteMemoryRepository(db_path=db_file)

    # Check that entries survived
    recovered_e1 = repo_session_2.get_by_id(e1.id)
    assert recovered_e1 is not None
    assert recovered_e1.content == "Foco em valuation pelo método de Graham"
    assert recovered_e1.category == "valuation"

    # Check search still works on recovered data
    graham_results = repo_session_2.search_text("Graham")
    assert len(graham_results) == 1
    assert graham_results[0].id == e1.id

    selic_results = repo_session_2.search_text("Selic")
    assert len(selic_results) == 1
    assert selic_results[0].id == e2.id

    # Check category filter
    rules = repo_session_2.list_by_user("default", category="rule")
    assert len(rules) == 1
    assert rules[0].id == e2.id

    # Check upsert updates existing entry
    updated_e1 = MemoryEntry.create(
        "Foco em valuation pelo método de Graham com margem de segurança de 30%",
        category="valuation",
        user_id="default",
        memory_id=e1.id,
    )
    repo_session_2.save(updated_e1)

    refetched = repo_session_2.get_by_id(e1.id)
    assert refetched is not None
    assert "margem de segurança" in refetched.content

    # Total count remains 2 (upsert did not duplicate)
    assert len(repo_session_2.list_by_user("default")) == 2
