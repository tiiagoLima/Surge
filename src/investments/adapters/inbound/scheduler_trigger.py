"""Scheduler trigger — runs InvestmentScannerUseCase on a cron schedule."""

from __future__ import annotations

import logging
from collections.abc import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class SchedulerTrigger:
    """Wraps APScheduler to periodically invoke a callable (usually use_case.execute)."""

    def __init__(self, timezone: str = "America/Sao_Paulo") -> None:
        self._scheduler = BlockingScheduler(timezone=timezone)
        self._timezone = timezone

    def schedule_daily(
        self,
        func: Callable[[], None],
        hour: int = 18,
        minute: int = 0,
        day_of_week: str = "mon-fri",
    ) -> None:
        """Schedule func daily on weekdays at hour:minute."""
        trigger = CronTrigger(
            day_of_week=day_of_week, hour=hour, minute=minute, timezone=self._timezone
        )
        self._scheduler.add_job(func, trigger, id="surge_daily_scan", replace_existing=True)
        logger.info(
            "Scheduled job 'surge_daily_scan' at %02d:%02d %s (%s)",
            hour,
            minute,
            day_of_week,
            self._timezone,
        )

    def schedule_interval(self, func: Callable[[], None], minutes: int = 5) -> None:
        """Schedule func repeatedly at a fixed interval."""
        self._scheduler.add_job(
            func,
            "interval",
            minutes=minutes,
            id="surge_email_poll",
            replace_existing=True,
        )
        logger.info("Scheduled job 'surge_email_poll' every %d minutes", minutes)

    def start(self) -> None:
        """Blocking start — runs until interrupted."""
        logger.info("Surge scheduler starting (timezone=%s)", self._timezone)
        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")

    def shutdown(self) -> None:
        """Graceful shutdown."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
