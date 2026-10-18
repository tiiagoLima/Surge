"""Execution lifecycle domain model and state machine."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from src.agent.domain.capabilities import CapabilityRequirements, RequirementLevel
from src.agent.domain.provider_health import ProviderFailure


class ExecutionStatus(StrEnum):
    """States in the execution lifecycle."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    WAITING_FOR_MODEL = "waiting_for_model"


_TERMINAL_STATUSES = {ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED}
_ALLOWED_TRANSITIONS = {
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.WAITING_FOR_MODEL,
    },
    ExecutionStatus.WAITING_FOR_MODEL: {ExecutionStatus.RUNNING, ExecutionStatus.FAILED},
}
_MAX_RESULT_SUMMARY_LENGTH = 500
_FORBIDDEN_SUMMARY_TERMS = (
    "api_key",
    "access_token",
    "password",
    "prompt",
    "payload",
    "traceback",
    "credential",
    "secret",
    "sdk",
    "exception",
)


def _validate_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_utc(value: datetime | None, field_name: str, *, required: bool = False) -> None:
    if value is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ValueError(f"{field_name} must be an aware UTC datetime")


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ExecutionRecord:
    """Immutable execution record with validated lifecycle timestamps and outcomes."""

    id: str
    capability_id: str
    trigger: str
    requirements: CapabilityRequirements
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    failure: ProviderFailure | None = None
    result_summary: str = ""

    def __post_init__(self) -> None:
        _validate_non_empty(self.id, "id")
        _validate_non_empty(self.capability_id, "capability_id")
        _validate_non_empty(self.trigger, "trigger")
        if not isinstance(self.requirements, CapabilityRequirements):
            raise ValueError("requirements must be a CapabilityRequirements instance")
        _validate_utc(self.created_at, "created_at", required=True)
        _validate_utc(self.started_at, "started_at")
        _validate_utc(self.finished_at, "finished_at")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at cannot precede created_at")
        if self.finished_at is not None and (
            self.started_at is None or self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must follow started_at")
        if not isinstance(self.status, ExecutionStatus):
            raise ValueError("status must be an ExecutionStatus")
        if self.failure is not None and not isinstance(self.failure, ProviderFailure):
            raise ValueError("failure must be a ProviderFailure or None")
        if not isinstance(self.result_summary, str):
            raise ValueError("result_summary must be a string")
        if len(self.result_summary) > _MAX_RESULT_SUMMARY_LENGTH:
            raise ValueError("result_summary is too long")
        lowered_summary = self.result_summary.casefold()
        if any(term in lowered_summary for term in _FORBIDDEN_SUMMARY_TERMS):
            raise ValueError("result_summary contains forbidden sensitive detail")

        if self.status is ExecutionStatus.PENDING:
            if self.started_at is not None or self.finished_at is not None or self.failure:
                raise ValueError("pending execution cannot have started, finished, or failure data")
        elif self.status is ExecutionStatus.RUNNING:
            if self.started_at is None or self.finished_at is not None or self.failure:
                raise ValueError("running execution requires started_at and no finish or failure")
        elif self.status is ExecutionStatus.SUCCEEDED:
            if self.started_at is None or self.finished_at is None or self.failure:
                raise ValueError("succeeded execution requires timestamps and no failure")
        elif self.status is ExecutionStatus.FAILED:
            if self.started_at is None or self.finished_at is None or self.failure is None:
                raise ValueError("failed execution requires timestamps and failure")
        elif self.status is ExecutionStatus.WAITING_FOR_MODEL:
            if self.started_at is None or self.finished_at is not None or self.failure is None:
                raise ValueError("waiting execution requires started_at and retryable failure")
            if not self.failure.retryable or self.requirements.llm is RequirementLevel.NOT_REQUIRED:
                raise ValueError("waiting requires retryable failure and an LLM requirement")

    @classmethod
    def create(
        cls,
        capability_id: str,
        trigger: str,
        requirements: CapabilityRequirements,
        *,
        execution_id: str | None = None,
        created_at: datetime | None = None,
    ) -> ExecutionRecord:
        """Create a stable-ID pending execution at the current UTC instant."""
        return cls(
            id=execution_id or str(uuid4()),
            capability_id=capability_id,
            trigger=trigger,
            requirements=requirements,
            created_at=created_at or _now_utc(),
        )

    @classmethod
    def new(cls, *args: object, **kwargs: object) -> ExecutionRecord:
        """Alias for create, retained as a concise domain construction API."""
        return cls.create(*args, **kwargs)  # type: ignore[arg-type]

    def transition(
        self,
        status: ExecutionStatus,
        *,
        at: datetime | None = None,
        failure: ProviderFailure | None = None,
        result_summary: str | None = None,
    ) -> ExecutionRecord:
        """Return a new record after applying one allowed lifecycle transition."""
        if not isinstance(status, ExecutionStatus):
            raise ValueError("status must be an ExecutionStatus")
        if status not in _ALLOWED_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Invalid execution transition: {self.status} -> {status}")
        instant = at or _now_utc()
        if self.status is ExecutionStatus.PENDING and status is ExecutionStatus.RUNNING:
            return replace(self, status=status, started_at=instant)
        if status is ExecutionStatus.RUNNING:
            return replace(self, status=status, failure=None, finished_at=None)
        if status is ExecutionStatus.WAITING_FOR_MODEL:
            return replace(
                self,
                status=status,
                failure=failure,
                result_summary=(
                    result_summary if result_summary is not None else self.result_summary
                ),
            )
        return replace(
            self,
            status=status,
            finished_at=instant,
            failure=failure if status is ExecutionStatus.FAILED else None,
            result_summary=result_summary if result_summary is not None else self.result_summary,
        )

    def start(self, *, at: datetime | None = None) -> ExecutionRecord:
        """Transition pending or waiting execution to running."""
        return self.transition(ExecutionStatus.RUNNING, at=at)

    def succeed(self, result_summary: str = "", *, at: datetime | None = None) -> ExecutionRecord:
        """Complete a running execution successfully."""
        return self.transition(ExecutionStatus.SUCCEEDED, at=at, result_summary=result_summary)

    def fail(
        self, failure: ProviderFailure, *, at: datetime | None = None, result_summary: str = ""
    ) -> ExecutionRecord:
        """Complete a running or waiting execution with a normalized failure."""
        return self.transition(
            ExecutionStatus.FAILED, at=at, failure=failure, result_summary=result_summary
        )

    def wait_for_model(
        self, failure: ProviderFailure, *, result_summary: str = ""
    ) -> ExecutionRecord:
        """Pause a running execution for a retryable model failure."""
        return self.transition(
            ExecutionStatus.WAITING_FOR_MODEL, failure=failure, result_summary=result_summary
        )
