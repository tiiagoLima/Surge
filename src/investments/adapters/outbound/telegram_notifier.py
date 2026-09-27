"""Telegram notifier — NotificationPort via Bot API."""

from __future__ import annotations

import logging

import requests

from src.investments.domain.models import Opportunity
from src.investments.domain.ports import NotificationPort

logger = logging.getLogger(__name__)


class TelegramNotifier(NotificationPort):
    """Sends Telegram messages via Bot API."""

    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True) -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._enabled = enabled

    def _send(self, text: str) -> None:
        if not self._enabled:
            return
        if not self._token or not self._chat_id:
            logger.warning("Telegram not configured — skipping")
            return
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()

    def notify(self, opportunities: list[Opportunity]) -> None:
        if not opportunities:
            return
        lines = ["*Surge* detectou quedas relevantes:\n"]
        for opp in opportunities:
            # Escape Markdown minimally — keep summary plain
            lines.append(f"• {opp.summary()}")
        text = "\n".join(lines)
        try:
            self._send(text)
            logger.info("Telegram sent (%d opportunities)", len(opportunities))
        except Exception:
            logger.exception("Failed to send Telegram message")
            raise

    def notify_error(self, message: str) -> None:
        try:
            self._send(f"⚠️ Surge erro: {message}")
        except Exception:
            logger.exception("Failed to send Telegram error")
