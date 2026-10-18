"""Normalize provider exceptions without exposing SDK payloads or credentials."""

import re

from src.agent.domain.provider_health import ProviderFailure, ProviderFailureKind


class ProviderError(Exception):
    """Neutral error preserving the original exception for explicit diagnostics only."""

    def __init__(self, failure: ProviderFailure, original_exception: Exception) -> None:
        self.failure = failure
        self.original_exception = original_exception
        super().__init__(failure.message)


def sanitize_error_message(message: str) -> str:
    """Mask common credentials; never log raw SDK payloads even after masking."""
    message = re.sub(r"AIza[\w-]+", "[REDACTED]", message)
    message = re.sub(r"\bsk-[\w-]+", "[REDACTED]", message)
    message = re.sub(r"(?i)(bearer\s+)[\w.+/=-]+", r"\1[REDACTED]", message)
    message = re.sub(
        r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret)"
        r"[\"']?\s*[:=]\s*[\"']?)[^\s,;\"'&}]+",
        r"\1[REDACTED]",
        message,
    )
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", message)


def classify_provider_exception(
    exc: Exception, provider: str = "gemini", model: str = ""
) -> ProviderFailure:
    """Classify status/code/message signals, returning only fixed safe messages.

    Provider/model arguments provide call-site context but are intentionally not
    echoed: SDK exceptions and identifiers may contain credentials or user data.
    """
    text = str(exc).upper()
    signals = [text]
    for attribute in ("code", "status_code", "status"):
        signals.append(str(getattr(exc, attribute, "")).upper())
    response = getattr(exc, "response", None)
    signals.append(str(getattr(response, "status_code", "")))
    signal = " ".join(signals)

    def matches(*values: str) -> bool:
        return any(re.search(rf"\b{re.escape(value)}\b", signal) for value in values)

    kind = ProviderFailureKind.UNKNOWN
    retryable = False
    if matches("401", "403", "PERMISSION_DENIED", "API_KEY_INVALID", "UNAUTHENTICATED"):
        kind = ProviderFailureKind.AUTHENTICATION
    elif matches("404", "NOT_FOUND") or any(
        value in signal
        for value in (
            "NÃO CONFIGURADA",
            "EMPTY API KEY",
            "API KEY IS EMPTY",
            "CHAVE VAZIA",
            "GOOGLE-GENAI' NÃO",
        )
    ):
        kind = ProviderFailureKind.CONFIGURATION
    elif matches("429", "RESOURCE_EXHAUSTED", "QUOTA"):
        kind, retryable = ProviderFailureKind.RATE_LIMIT, True
    elif isinstance(exc, TimeoutError) or matches("504", "DEADLINE_EXCEEDED", "TIMEOUT"):
        kind, retryable = ProviderFailureKind.TIMEOUT, True
    elif matches("503", "500", "UNAVAILABLE"):
        kind, retryable = ProviderFailureKind.TEMPORARY_UNAVAILABLE, True
    elif matches("400", "INVALID_ARGUMENT", "BAD_REQUEST"):
        kind = ProviderFailureKind.INVALID_REQUEST
    messages = {
        ProviderFailureKind.AUTHENTICATION: "Falha de autenticação do provedor.",
        ProviderFailureKind.CONFIGURATION: "Configuração do provedor indisponível ou inválida.",
        ProviderFailureKind.RATE_LIMIT: "Limite de uso do provedor atingido.",
        ProviderFailureKind.TIMEOUT: "Tempo limite de resposta do provedor excedido.",
        ProviderFailureKind.TEMPORARY_UNAVAILABLE: "Provedor temporariamente indisponível.",
        ProviderFailureKind.INVALID_REQUEST: "Solicitação rejeitada pelo provedor.",
        ProviderFailureKind.UNKNOWN: "Falha não identificada no provedor.",
    }
    return ProviderFailure(kind, messages[kind], retryable)
