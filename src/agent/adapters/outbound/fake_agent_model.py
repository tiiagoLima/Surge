"""In-memory fake agent model adapter for fast, deterministic unit testing."""

from __future__ import annotations

from src.agent.domain.models import AgentMessage, ToolDefinition
from src.agent.domain.ports import AgentModelPort


class FakeAgentModel(AgentModelPort):
    """Simulated AI model that returns preconfigured messages or behaves predictably."""

    def __init__(self, responses: list[AgentMessage] | None = None) -> None:
        self._responses: list[AgentMessage] = list(responses or [])
        self.calls: list[tuple[list[AgentMessage], list[ToolDefinition] | None]] = []

    def queue_response(self, message: AgentMessage) -> None:
        """Add a response to the queue."""
        self._responses.append(message)

    def generate_reply(
        self,
        messages: list[AgentMessage],
        tools: list[ToolDefinition] | None = None,
    ) -> AgentMessage:
        """Record the call and return the next queued response or a fallback."""
        self.calls.append((list(messages), list(tools) if tools else None))
        if self._responses:
            return self._responses.pop(0)

        return AgentMessage(
            role="assistant",
            content="Resposta simulada pelo modelo fake.",
        )
