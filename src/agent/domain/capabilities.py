"""Pure capability declarations and operational requirement matching."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


def _validate_capability_id(capability_id: str) -> None:
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise ValueError("Capability id must be a non-empty string")


class RequirementLevel(StrEnum):
    """Declare whether a resource is necessary, enriching, or unused."""

    NOT_REQUIRED = "not_required"
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass(frozen=True)
class CapabilityRequirements:
    """Resource demand, independent of runtime availability and providers."""

    llm: RequirementLevel = RequirementLevel.NOT_REQUIRED
    network: RequirementLevel = RequirementLevel.NOT_REQUIRED
    storage: RequirementLevel = RequirementLevel.NOT_REQUIRED

    def __post_init__(self) -> None:
        for field_name in ("llm", "network", "storage"):
            if not isinstance(getattr(self, field_name), RequirementLevel):
                raise ValueError(f"{field_name} must be a RequirementLevel")


@dataclass(frozen=True)
class RuntimeAvailability:
    """Resources declared available at runtime, without service health probes."""

    llm: bool = False
    network: bool = False
    storage: bool = False

    def __post_init__(self) -> None:
        for field_name in ("llm", "network", "storage"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a bool")


@dataclass(frozen=True)
class CapabilityDefinition:
    """Immutable capability identity and its operational requirements."""

    id: str
    requirements: CapabilityRequirements

    def __post_init__(self) -> None:
        _validate_capability_id(self.id)
        if not isinstance(self.requirements, CapabilityRequirements):
            raise ValueError("requirements must be a CapabilityRequirements instance")


class CapabilityRegistry:
    """Register capabilities and evaluate requirements without external I/O."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}

    def register(self, capability: CapabilityDefinition) -> None:
        """Register a capability, rejecting invalid or duplicate identities."""
        _validate_capability_id(capability.id)
        if capability.id in self._capabilities:
            raise ValueError(f"Capability already registered: {capability.id}")
        self._capabilities[capability.id] = capability

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        """Return a registered capability, or None if absent."""
        return self._capabilities.get(capability_id)

    def list_capabilities(self) -> list[CapabilityDefinition]:
        """Return capabilities in registration order as a separate list."""
        return list(self._capabilities.values())

    def is_eligible(self, capability_id: str, available: RuntimeAvailability) -> bool:
        """Check required resources; raise KeyError for an unknown capability."""
        requirements = self._capabilities[capability_id].requirements
        return all(
            getattr(requirements, dimension) != RequirementLevel.REQUIRED
            or getattr(available, dimension)
            for dimension in ("llm", "network", "storage")
        )

    def is_fully_supported(self, capability_id: str, available: RuntimeAvailability) -> bool:
        """Check required and optional resources; raise KeyError for an unknown ID."""
        requirements = self._capabilities[capability_id].requirements
        return all(
            getattr(requirements, dimension)
            not in (RequirementLevel.REQUIRED, RequirementLevel.OPTIONAL)
            or getattr(available, dimension)
            for dimension in ("llm", "network", "storage")
        )
