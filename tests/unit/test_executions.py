"""Offline tests for execution lifecycle domain invariants."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from src.agent.domain.capabilities import CapabilityRequirements, RequirementLevel
from src.agent.domain.executions import ExecutionRecord, ExecutionStatus
from src.agent.domain.provider_health import ProviderFailure, ProviderFailureKind

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
REQUIREMENTS = CapabilityRequirements(
    llm=RequirementLevel.OPTIONAL,
    network=RequirementLevel.REQUIRED,
    storage=RequirementLevel.REQUIRED,
)
RETRYABLE = ProviderFailure(ProviderFailureKind.TIMEOUT, "safe timeout", True)
PERMANENT = ProviderFailure(ProviderFailureKind.AUTHENTICATION, "safe auth failure", False)


def test_create_is_pending_with_stable_id_and_utc_timestamp() -> None:
    record = ExecutionRecord.create(
        "investment.scan_portfolio",
        "scheduler",
        REQUIREMENTS,
        execution_id="exec-1",
        created_at=NOW,
    )
    assert record.id == "exec-1"
    assert record.status is ExecutionStatus.PENDING
    assert record.created_at == NOW
    assert record.started_at is None
    with pytest.raises(FrozenInstanceError):
        record.status = ExecutionStatus.RUNNING


def test_state_machine_and_terminal_states() -> None:
    pending = ExecutionRecord.create(
        "agent.ask", "cli", CapabilityRequirements(llm=RequirementLevel.REQUIRED), created_at=NOW
    )
    running = pending.start(at=NOW + timedelta(seconds=1))
    succeeded = running.succeed("answer", at=NOW + timedelta(seconds=2))
    assert running.status is ExecutionStatus.RUNNING
    assert succeeded.status is ExecutionStatus.SUCCEEDED
    assert succeeded.finished_at == NOW + timedelta(seconds=2)
    with pytest.raises(ValueError):
        pending.succeed("bad")
    with pytest.raises(ValueError):
        succeeded.start()
    with pytest.raises(ValueError):
        running.fail(PERMANENT, at=NOW + timedelta(seconds=2), result_summary="failed").start()


def test_waiting_requires_retryable_failure_and_llm_requirement() -> None:
    running = ExecutionRecord.create(
        "agent.ask", "cli", CapabilityRequirements(llm=RequirementLevel.REQUIRED), created_at=NOW
    ).start(at=NOW)
    waiting = running.wait_for_model(RETRYABLE, result_summary="will retry")
    assert waiting.status is ExecutionStatus.WAITING_FOR_MODEL
    assert waiting.failure == RETRYABLE
    resumed = waiting.start(at=NOW + timedelta(seconds=1))
    assert resumed.status is ExecutionStatus.RUNNING
    with pytest.raises(ValueError):
        running.wait_for_model(PERMANENT)
    no_llm = ExecutionRecord.create(
        "portfolio.get_holdings", "cli", CapabilityRequirements(), created_at=NOW
    ).start(at=NOW)
    with pytest.raises(ValueError):
        no_llm.wait_for_model(RETRYABLE)


def test_failed_execution_requires_normalized_failure() -> None:
    running = ExecutionRecord.create("agent.ask", "cli", REQUIREMENTS, created_at=NOW).start(at=NOW)
    failed = running.fail(PERMANENT, at=NOW + timedelta(seconds=1), result_summary="not available")
    assert failed.status is ExecutionStatus.FAILED
    assert failed.failure == PERMANENT
    with pytest.raises(ValueError):
        ExecutionRecord(
            id="x",
            capability_id="cap",
            trigger="test",
            requirements=REQUIREMENTS,
            created_at=NOW,
            started_at=NOW,
            finished_at=NOW,
            status=ExecutionStatus.FAILED,
        )


def test_timestamps_must_be_aware_utc_and_ordered() -> None:
    with pytest.raises(ValueError):
        ExecutionRecord.create(
            "cap", "test", CapabilityRequirements(), created_at=datetime(2026, 1, 1)
        )
    with pytest.raises(ValueError):
        ExecutionRecord(
            id="x",
            capability_id="cap",
            trigger="test",
            requirements=CapabilityRequirements(),
            created_at=NOW,
            started_at=NOW - timedelta(seconds=1),
            status=ExecutionStatus.RUNNING,
        )


def test_sensitive_or_oversized_result_summary_is_rejected() -> None:
    running = ExecutionRecord.create("cap", "test", CapabilityRequirements(), created_at=NOW).start(
        at=NOW
    )
    with pytest.raises(ValueError):
        running.succeed("prompt=private")
    with pytest.raises(ValueError):
        running.succeed("x" * 501)
