"""Offline tests for the execution coordinator and operational state."""

from __future__ import annotations

from src.agent.application.execution_coordinator import ExecutionCoordinator
from src.agent.domain.capabilities import (
    CapabilityDefinition,
    CapabilityRegistry,
    CapabilityRequirements,
    RequirementLevel,
    RuntimeAvailability,
)
from src.agent.domain.executions import ExecutionRecord, ExecutionStatus
from src.agent.domain.operational_state import OperationalMode, OperationalState
from src.agent.domain.ports import ExecutionRecordPort
from src.agent.domain.provider_health import (
    ProviderFailure,
    ProviderFailureKind,
    ProviderHealth,
    ProviderHealthStatus,
)


class FakeExecutionRepository(ExecutionRecordPort):
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[ExecutionRecord] = []
        self.fail = fail

    def save(self, record: ExecutionRecord) -> None:
        if self.fail:
            raise OSError("storage unavailable")
        self.records.append(record)

    def get_by_id(self, execution_id: str) -> ExecutionRecord | None:
        return next((record for record in self.records if record.id == execution_id), None)


def _registry(capability_id: str, requirements: CapabilityRequirements) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(CapabilityDefinition(capability_id, requirements))
    return registry


def _health(status: ProviderHealthStatus) -> ProviderHealth:
    return ProviderHealth("fake", "model", status)


def test_deterministic_operation_runs_without_llm_and_persists_lifecycle() -> None:
    repository = FakeExecutionRepository()
    calls: list[str] = []
    coordinator = ExecutionCoordinator(
        _registry("portfolio.get_holdings", CapabilityRequirements()),
        RuntimeAvailability(storage=True),
        repository,
    )

    result = coordinator.execute("portfolio.get_holdings", "cli", lambda: calls.append("called"))

    assert result.status is ExecutionStatus.SUCCEEDED
    assert calls == ["called"]
    assert [record.status for record in repository.records] == [
        ExecutionStatus.PENDING,
        ExecutionStatus.RUNNING,
        ExecutionStatus.SUCCEEDED,
    ]


def test_required_model_without_health_waits_without_running_operation() -> None:
    calls: list[str] = []
    coordinator = ExecutionCoordinator(
        _registry("agent.ask", CapabilityRequirements(llm=RequirementLevel.REQUIRED)),
        RuntimeAvailability(llm=False),
        FakeExecutionRepository(),
    )

    result = coordinator.execute("agent.ask", "cli", lambda: calls.append("called"))

    assert result.status is ExecutionStatus.WAITING_FOR_MODEL
    assert result.failure is not None and result.failure.retryable
    assert calls == []


def test_optional_llm_runs_in_degraded_mode() -> None:
    coordinator = ExecutionCoordinator(
        _registry("investment.scan", CapabilityRequirements(llm=RequirementLevel.OPTIONAL)),
        RuntimeAvailability(),
    )

    result = coordinator.execute("investment.scan", "scheduler", lambda: None)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert coordinator.operational_state.mode is OperationalMode.DEGRADED
    assert "llm_unavailable" in coordinator.operational_state.reasons


def test_required_network_or_storage_fails_before_operation() -> None:
    for resource in ("network", "storage"):
        calls: list[str] = []
        requirements = CapabilityRequirements(**{resource: RequirementLevel.REQUIRED})
        coordinator = ExecutionCoordinator(
            _registry(f"needs.{resource}", requirements), RuntimeAvailability()
        )
        result = coordinator.execute(
            f"needs.{resource}", "test", lambda calls=calls: calls.append("called")
        )
        assert result.status is ExecutionStatus.FAILED
        assert result.failure is not None and resource in result.failure.message
        assert calls == []


def test_retryable_provider_failure_waits_but_non_retryable_fails() -> None:
    scenarios = (
        (True, ExecutionStatus.WAITING_FOR_MODEL),
        (False, ExecutionStatus.FAILED),
    )
    for retryable, expected in scenarios:
        failure = ProviderFailure(ProviderFailureKind.TIMEOUT, "safe failure", retryable)

        coordinator = ExecutionCoordinator(
            _registry("cognitive", CapabilityRequirements(llm=RequirementLevel.REQUIRED)),
            RuntimeAvailability(llm=True),
            health=_health(ProviderHealthStatus.AVAILABLE),
        )

        # Provider-neutral exceptions are normalized as unknown; use a failure-bearing error.
        class FailureError(Exception):
            pass

        error = FailureError("safe")
        error.failure = failure  # type: ignore[attr-defined]
        result = coordinator.execute(
            "cognitive", "test", lambda error=error: (_ for _ in ()).throw(error)
        )
        assert result.status is expected


def test_failed_operation_does_not_interrupt_next_execution() -> None:
    coordinator = ExecutionCoordinator(
        _registry("independent", CapabilityRequirements()), RuntimeAvailability()
    )

    failed = coordinator.execute(
        "independent", "first", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    succeeded = coordinator.execute("independent", "second", lambda: None)

    assert failed.status is ExecutionStatus.FAILED
    assert succeeded.status is ExecutionStatus.SUCCEEDED


def test_storage_failure_returns_explicit_non_durable_result() -> None:
    coordinator = ExecutionCoordinator(
        _registry("local", CapabilityRequirements()),
        RuntimeAvailability(),
        FakeExecutionRepository(fail=True),
    )

    result = coordinator.execute("local", "test", lambda: None)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert "not durable" in result.result_summary


def test_operational_state_uses_health_not_configuration_alone() -> None:
    availability = RuntimeAvailability(llm=True, network=True, storage=True)
    state = OperationalState.derive(availability, _health(ProviderHealthStatus.DEGRADED))
    assert state.mode is OperationalMode.DEGRADED
    assert state.reasons == ("llm_health_degraded",)

    normal = OperationalState.derive(availability, _health(ProviderHealthStatus.AVAILABLE))
    assert normal.mode is OperationalMode.NORMAL
    assert normal.reasons == ()
