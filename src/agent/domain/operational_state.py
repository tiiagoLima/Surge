"""Immutable global operational state derived from runtime observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.agent.domain.capabilities import RuntimeAvailability
from src.agent.domain.provider_health import ProviderHealth, ProviderHealthStatus


class OperationalMode(StrEnum):
    """Global execution mode exposed to orchestration and observability."""

    NORMAL = "normal"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class OperationalState:
    """Derived, non-persisted state of the runtime resource landscape."""

    mode: OperationalMode
    availability: RuntimeAvailability
    health: ProviderHealth | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OperationalMode):
            raise ValueError("mode must be an OperationalMode")
        if not isinstance(self.availability, RuntimeAvailability):
            raise ValueError("availability must be a RuntimeAvailability")
        if self.health is not None and not isinstance(self.health, ProviderHealth):
            raise ValueError("health must be a ProviderHealth or None")
        if not isinstance(self.reasons, tuple) or not all(
            isinstance(reason, str) and reason.strip() for reason in self.reasons
        ):
            raise ValueError("reasons must be a tuple of non-empty strings")

    @classmethod
    def derive(
        cls,
        availability: RuntimeAvailability,
        health: ProviderHealth | None = None,
    ) -> OperationalState:
        """Derive NORMAL/DEGRADED without probing providers or persisting state."""
        reasons: list[str] = []
        for resource in ("llm", "network", "storage"):
            if not getattr(availability, resource):
                reasons.append(f"{resource}_unavailable")
        if health is None:
            if availability.llm:
                reasons.append("llm_health_unobserved")
        elif health.status is not ProviderHealthStatus.AVAILABLE:
            reasons.append(f"llm_health_{health.status.value}")
        mode = OperationalMode.NORMAL if not reasons else OperationalMode.DEGRADED
        return cls(mode=mode, availability=availability, health=health, reasons=tuple(reasons))
