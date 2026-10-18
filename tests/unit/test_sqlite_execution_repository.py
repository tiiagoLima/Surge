"""Offline SQLite adapter tests for execution lifecycle records."""

from datetime import UTC, datetime, timedelta

from src.agent.adapters.outbound.sqlite_execution_repository import SqliteExecutionRepository
from src.agent.domain.capabilities import CapabilityRequirements, RequirementLevel
from src.agent.domain.executions import ExecutionRecord
from src.agent.domain.provider_health import ProviderFailure, ProviderFailureKind

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def _record(execution_id: str = "exec-1") -> ExecutionRecord:
    requirements = CapabilityRequirements(
        llm=RequirementLevel.OPTIONAL,
        network=RequirementLevel.REQUIRED,
        storage=RequirementLevel.REQUIRED,
    )
    return (
        ExecutionRecord.create(
            "investment.scan_portfolio",
            "scheduler",
            requirements,
            execution_id=execution_id,
            created_at=NOW,
        )
        .start(at=NOW + timedelta(seconds=1))
        .fail(
            ProviderFailure(ProviderFailureKind.TIMEOUT, "safe timeout", True),
            at=NOW + timedelta(seconds=2),
            result_summary="degraded",
        )
    )


def test_round_trip_failure_and_tri_state_requirements(tmp_path) -> None:
    path = tmp_path / "executions.db"
    repository = SqliteExecutionRepository(path)
    record = _record()
    repository.save(record)
    loaded = repository.get_by_id(record.id)
    assert loaded == record
    assert loaded.failure is not None
    assert loaded.failure.kind is ProviderFailureKind.TIMEOUT
    assert loaded.requirements.llm is RequirementLevel.OPTIONAL
    assert path.exists()


def test_upsert_replaces_same_id_and_null_failure(tmp_path) -> None:
    repository = SqliteExecutionRepository(tmp_path / "executions.db")
    record = _record("same-id")
    repository.save(record)
    succeeded = (
        ExecutionRecord.create(
            "investment.scan_portfolio",
            "scheduler",
            record.requirements,
            execution_id="same-id",
            created_at=NOW,
        )
        .start(at=NOW + timedelta(seconds=3))
        .succeed("done", at=NOW + timedelta(seconds=4))
    )
    repository.save(succeeded)
    assert repository.get_by_id("same-id") == succeeded
    assert repository.get_by_id("missing") is None


def test_reopen_and_idempotent_ddl(tmp_path) -> None:
    path = tmp_path / "executions.db"
    first = SqliteExecutionRepository(path)
    first.save(_record())
    second = SqliteExecutionRepository(path)
    assert second.get_by_id("exec-1") == _record()


def test_memory_database_keeps_anchor_and_isolated_instances() -> None:
    repository = SqliteExecutionRepository(":memory:")
    record = _record()
    repository.save(record)
    assert repository.get_by_id(record.id) == record
    other = SqliteExecutionRepository(":memory:")
    assert other.get_by_id(record.id) is None


def test_sensitive_fields_are_not_stored(tmp_path) -> None:
    path = tmp_path / "executions.db"
    repository = SqliteExecutionRepository(path)
    repository.save(_record())
    raw = path.read_bytes()
    assert b"secret" not in raw
    assert b"traceback" not in raw
    assert b"prompt" not in raw
