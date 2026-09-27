"""Composite notifier — fans out to multiple NotificationPorts."""

from __future__ import annotations

import logging

from src.investments.domain.models import Opportunity
from src.investments.domain.ports import NotificationPort

logger = logging.getLogger(__name__)


class CompositeNotifier(NotificationPort):
    """Delegates to multiple notifiers (email + telegram). Failures in one don't block others."""

    def __init__(self, notifiers: list[NotificationPort]) -> None:
        self._notifiers = notifiers

    def notify(self, opportunities: list[Opportunity]) -> None:
        for n in self._notifiers:
            try:
                n.notify(opportunities)
            except Exception:
                logger.exception("Notifier %s failed on notify", type(n).__name__)

    def notify_error(self, message: str) -> None:
        for n in self._notifiers:
            try:
                n.notify_error(message)
            except Exception:
                logger.exception("Notifier %s failed on notify_error", type(n).__name__)
