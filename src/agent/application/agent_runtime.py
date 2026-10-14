"""Agent runtime managing conversation loop, model turns, and tool dispatch."""

from __future__ import annotations

import logging

from src.agent.application.tool_registry import ToolRegistry
from src.agent.domain.models import AgentMessage
from src.agent.domain.ports import AgentModelPort

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "Você é o Surge, um assistente pessoal para finanças e investimentos. "
    "Responda ao usuário em português de forma concisa, educada e factual. "
    "Você NÃO é um assistente de programação ou desenvolvimento de software. "
    "Recuse educadamente qualquer pedido para escrever, revisar, debugar ou executar código, "
    "bem como pedidos para acessar arquivos locais, sistema de arquivos ou comandos de terminal. "
    "Consulte as ferramentas disponíveis quando o usuário perguntar sobre sua carteira. "
    "Ao relatar dados retornados pelas ferramentas, use apenas os valores exatos fornecidos. "
    "Se a carteira estiver vazia, informe que o usuário não possui ativos cadastrados. "
    "Nunca invente ativos, cotações, preços ou cálculos não fornecidos. "
    "Não recomende compra, venda ou alocação de ativos."
)


class AgentRuntime:
    """Orchestrates multi-turn conversation rounds with tool execution and safety limits."""

    def __init__(
        self,
        model: AgentModelPort,
        tool_registry: ToolRegistry,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        default_max_model_turns: int = 3,
    ) -> None:
        self._model = model
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt
        self._default_max_model_turns = default_max_model_turns

    def run(self, user_prompt: str, max_model_turns: int | None = None) -> str:
        """Execute a conversational round responding to user prompt with tool calling."""
        cleaned_prompt = str(user_prompt).strip()
        if not cleaned_prompt:
            return "Por favor, envie uma mensagem ou pergunta."

        max_turns = max_model_turns or self._default_max_model_turns
        messages: list[AgentMessage] = [
            AgentMessage(role="system", content=self._system_prompt),
            AgentMessage(role="user", content=cleaned_prompt),
        ]

        tools = self._tool_registry.get_definitions()
        turns = 0

        while turns < max_turns:
            turns += 1
            try:
                reply = self._model.generate_reply(messages, tools=tools)
            except Exception:
                logger.exception("Falha na comunicação com o modelo de inteligência artificial.")
                return (
                    "Desculpe, ocorreu uma falha ao comunicar com o modelo de IA. "
                    "Por favor, tente novamente mais tarde."
                )

            messages.append(reply)

            if not reply.tool_calls:
                return (
                    reply.content or "Não foi possível gerar uma resposta para a sua solicitação."
                )

            for tool_call in reply.tool_calls:
                result = self._tool_registry.invoke(
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                    tool_call_id=tool_call.id,
                )
                messages.append(
                    AgentMessage(
                        role="tool",
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                        name=result.name,
                    )
                )

        logger.warning(
            "Agent runtime atingiu o limite de %d turnos de modelo sem resposta final.",
            max_turns,
        )
        return (
            "Não foi possível concluir sua resposta dentro do limite de iterações permitidas "
            f"({max_turns} chamadas ao modelo)."
        )
