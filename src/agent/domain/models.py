"""Domain models for the agent bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ToolDefinition:
    """Specification of a tool available to the agent."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    """Represents a tool execution requested by the agent model."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a tool execution."""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class AgentMessage:
    """A message in an agent interaction turn."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None
