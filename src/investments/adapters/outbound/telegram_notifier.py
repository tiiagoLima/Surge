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
            json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()

    def notify(self, opportunities: list[Opportunity]) -> None:
        if not opportunities:
            return

        chunk_limit = 4000
        current_chunk = "*Surge* detectou quedas relevantes:\n\n"
        chunks = []

        for opp in opportunities:
            line = f"• {opp.summary()}\n"
            if opp.insight:
                line += f"🧠 <b>Insight da IA:</b> {opp.insight}\n"

            # If the current line exceeds the limit, save the block and start a new one
            if len(current_chunk) + len(line) > chunk_limit:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += line

        # Adds the last remaining block to the list
        if current_chunk:
            chunks.append(current_chunk)

        try:
            # Sends each block sequentially
            for text in chunks:
                self._send(text)
            logger.info(
                "Telegram sent (%d opportunities in %d messages)", len(opportunities), len(chunks)
            )
        except Exception:
            logger.exception("Failed to send Telegram message")
            raise

    def notify_error(self, message: str) -> None:
        try:
            self._send(f"⚠️ Surge erro: {message}")
        except Exception:
            logger.exception("Failed to send Telegram error")
