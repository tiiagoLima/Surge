"""Ports for the agent bounded context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from src.agent.domain.executions import ExecutionRecord
from src.agent.domain.models import AgentMessage, ToolDefinition

ToolHandler = Callable[[dict[str, Any]], str]


class ExecutionRecordPort(ABC):
    """Port for storing and retrieving execution lifecycle records."""

    @abstractmethod
    def save(self, record: ExecutionRecord) -> None:
        """Persist or update an execution record."""

    @abstractmethod
    def get_by_id(self, execution_id: str) -> ExecutionRecord | None:
        """Retrieve an execution record by stable ID."""


class AgentModelPort(ABC):
    """Port for interacting with an AI model capable of reasoning and tool calling."""

    @abstractmethod
    def generate_reply(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AgentMessage:
        """Generate the next assistant response or tool call request given conversation history."""
