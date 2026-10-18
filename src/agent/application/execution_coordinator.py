"""Coordinate capability eligibility and isolated execution lifecycles."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.agent.domain.capabilities import (
    CapabilityRegistry,
    CapabilityRequirements,
    RequirementLevel,
    RuntimeAvailability,
)
from src.agent.domain.executions import ExecutionRecord
from src.agent.domain.operational_state import OperationalState
from src.agent.domain.ports import ExecutionRecordPort
from src.agent.domain.provider_health import (
    ProviderFailure,
    ProviderFailureKind,
    ProviderHealth,
    ProviderHealthStatus,
)

Operation = Callable[[], Any]


class ExecutionCoordinator:
    """Start eligible capabilities and isolate their lifecycle failures.

    The coordinator depends only on domain declarations, the execution port, and
    caller-provided operations. It does not know use cases, adapters, providers,
    retry policies, or schedulers.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        availability: RuntimeAvailability,
        execution_records: ExecutionRecordPort | None = None,
        health: ProviderHealth | None = None,
    ) -> None:
        self._registry = registry
        self._availability = availability
        self._execution_records = execution_records
        self._health = health

    @property
    def operational_state(self) -> OperationalState:
        """Return the current derived state without performing I/O."""
        return OperationalState.derive(self._availability, self._health)

    def execute(
        self,
        capability_id: str,
        trigger: str,
        operation: Operation,
    ) -> ExecutionRecord:
        """Execute one capability operation and return its final lifecycle record."""
        capability = self._registry.get(capability_id)
        if capability is None:
            raise KeyError(capability_id)
        if not callable(operation):
            raise ValueError("operation must be callable")

        record = ExecutionRecord.create(capability_id, trigger, capability.requirements)
        durable = self._persist(record)
        requirements = capability.requirements

        missing_required = self._missing_required(requirements)
        if missing_required:
            failure = self._resource_failure(missing_required)
            return self._finish_failure(record, failure, durable)

        if self._requires_model(requirements):
            failure = ProviderFailure(
                ProviderFailureKind.TEMPORARY_UNAVAILABLE,
                "Modelo necessário indisponível; execução aguardando retomada.",
                True,
            )
            running = record.start()
            durable = self._persist(running, durable)
            waiting = running.wait_for_model(failure, result_summary=_WAITING_SUMMARY)
            self._persist(waiting, durable)
            return waiting

        running = record.start()
        durable = self._persist(running, durable)
        try:
            operation()
        except Exception as exc:
            failure = self._failure_from_operation(exc)
            if failure.retryable and requirements.llm is not RequirementLevel.NOT_REQUIRED:
                result = running.wait_for_model(failure, result_summary=_WAITING_SUMMARY)
            else:
                result = running.fail(failure, result_summary=_FAILURE_SUMMARY)
        else:
            result = running.succeed(_SUCCESS_SUMMARY if durable else _SUCCESS_NOT_DURABLE_SUMMARY)
        self._persist(result, durable)
        return result

    def _persist(self, record: ExecutionRecord, durable: bool = True) -> bool:
        """Attempt persistence and report durability without masking repository errors."""
        if self._execution_records is None or not durable:
            return False
        try:
            self._execution_records.save(record)
        except Exception:
            return False
        return True

    def _missing_required(self, requirements: CapabilityRequirements) -> tuple[str, ...]:
        return tuple(
            resource
            for resource in ("network", "storage")
            if getattr(requirements, resource) is RequirementLevel.REQUIRED
            and not getattr(self._availability, resource)
        )

    def _requires_model(self, requirements: CapabilityRequirements) -> bool:
        if requirements.llm is not RequirementLevel.REQUIRED:
            return False
        if not self._availability.llm:
            return True
        return self._health is None or self._health.status is not ProviderHealthStatus.AVAILABLE

    def _resource_failure(self, resources: tuple[str, ...]) -> ProviderFailure:
        label = " e ".join(resources)
        return ProviderFailure(
            ProviderFailureKind.CONFIGURATION,
            f"Recurso obrigatório indisponível: {label}.",
            False,
        )

    @staticmethod
    def _failure_from_operation(exc: Exception) -> ProviderFailure:
        failure = getattr(exc, "failure", None)
        if isinstance(failure, ProviderFailure):
            return failure
        return ProviderFailure(
            ProviderFailureKind.UNKNOWN,
            "Falha não identificada durante a execução.",
            False,
        )

    def _finish_failure(
        self,
        record: ExecutionRecord,
        failure: ProviderFailure,
        durable: bool,
    ) -> ExecutionRecord:
        running = record.start()
        durable = self._persist(running, durable)
        result = running.fail(failure, result_summary=_FAILURE_SUMMARY)
        self._persist(result, durable)
        return result


_SUCCESS_SUMMARY = "Capability completed successfully."
_SUCCESS_NOT_DURABLE_SUMMARY = "Capability completed; execution record was not durable."
_FAILURE_SUMMARY = "Capability execution failed."
_WAITING_SUMMARY = "Capability is waiting for model availability."
