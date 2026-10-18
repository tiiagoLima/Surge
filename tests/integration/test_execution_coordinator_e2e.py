"""Offline composition-root E2E test for deterministic execution coordination."""

from __future__ import annotations

from src import main as composition_root
from src.agent.domain.executions import ExecutionStatus
from src.shared.database.migrations import create_memory_database


def test_composition_root_executes_existing_deterministic_capability_without_llm(
    monkeypatch,
) -> None:
    """Build the production capability registry and SQLite lifecycle port offline."""
    _, connection = create_memory_database()
    repository = composition_root.SqliteExecutionRepository(":memory:", connection=connection)
    coordinator = composition_root.build_execution_coordinator(
        availability=composition_root.RuntimeAvailability(storage=True),
        execution_records=repository,
    )
    calls: list[str] = []

    result = coordinator.execute(
        "portfolio.get_holdings",
        "offline-e2e",
        lambda: calls.append("deterministic-operation"),
    )

    persisted = repository.get_by_id(result.id)
    assert result.status is ExecutionStatus.SUCCEEDED
    assert persisted == result
    assert calls == ["deterministic-operation"]
    assert coordinator.operational_state.mode.value == "degraded"
