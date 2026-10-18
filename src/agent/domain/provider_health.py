"""Provider-neutral failures and observable health contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class ProviderFailureKind(StrEnum):
    """Stable failure categories independent of an SDK."""

    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    RATE_LIMIT = "rate_limit"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    TIMEOUT = "timeout"
    INVALID_REQUEST = "invalid_request"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderFailure:
    """Normalized failure; adapters supply a sanitized, non-sensitive message."""

    kind: ProviderFailureKind
    message: str
    retryable: bool

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProviderFailureKind):
            raise ValueError("kind must be a ProviderFailureKind")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message must be a non-empty sanitized string")
        if not isinstance(self.retryable, bool):
            raise ValueError("retryable must be a bool")


class ProviderHealthStatus(StrEnum):
    """Last observed availability of a provider/model pair."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProviderHealth:
    """Immutable in-memory health snapshot, not a guarantee of future success."""

    provider: str
    model: str
    status: ProviderHealthStatus
    failure: ProviderFailure | None = None

    def __post_init__(self) -> None:
        for field_name in ("provider", "model"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.status, ProviderHealthStatus):
            raise ValueError("status must be a ProviderHealthStatus")
        if self.failure is not None and not isinstance(self.failure, ProviderFailure):
            raise ValueError("failure must be a ProviderFailure or None")


class ProviderHealthPort(ABC):
    """Observe cached health or explicitly probe provider metadata."""

    @abstractmethod
    def get_health(self) -> ProviderHealth:
        """Return the last snapshot without I/O."""

    @abstractmethod
    def check_health(self) -> ProviderHealth:
        """Probe provider metadata without generating content."""
