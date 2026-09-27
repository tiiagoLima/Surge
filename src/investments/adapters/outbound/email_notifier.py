"""Email notifier — NotificationPort via SMTP with rich HTML templates."""

from __future__ import annotations

import logging
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import jinja2

from src.investments.domain.models import Opportunity
from src.investments.domain.ports import NotificationPort

logger = logging.getLogger(__name__)


class EmailNotifier(NotificationPort):
    """Sends email notifications with modern HTML templates and plain text fallback."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        email_from: str,
        email_to: str,
        enabled: bool = True,
        templates_dir: str | Path | None = None,
    ) -> None:
        self._host = smtp_host
        self._port = smtp_port
        self._user = smtp_user
        self._password = smtp_password
        self._from = email_from
        self._to = email_to
        self._enabled = enabled

        self._templates_dir = (
            Path(templates_dir)
            if templates_dir
            else Path(__file__).resolve().parent.parent.parent / "assets" / "templates"
        )
        self._jinja_env: jinja2.Environment | None = None
        if self._templates_dir.exists():
            self._jinja_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(self._templates_dir)),
                autoescape=jinja2.select_autoescape(["html", "xml"]),
            )

    def render_opportunities_html(self, opportunities: list[Opportunity]) -> str | None:
        """Render the HTML body for opportunity alerts."""
        if not self._jinja_env:
            return None
        try:
            template = self._jinja_env.get_template("opportunities.html")
            count = len(opportunities)
            threshold = opportunities[0].threshold_pct if opportunities else 5.0
            max_drop = max(abs(o.drop_pct) for o in opportunities) if opportunities else None
            generated_at = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
            return template.render(
                opportunities=opportunities,
                count=count,
                threshold=threshold,
                max_drop=max_drop,
                generated_at=generated_at,
            )
        except Exception:
            logger.exception("Failed to render opportunities HTML template")
            return None

    def render_error_html(self, message: str) -> str | None:
        """Render the HTML body for system error alerts."""
        if not self._jinja_env:
            return None
        try:
            template = self._jinja_env.get_template("error.html")
            generated_at = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
            return template.render(
                message=message,
                generated_at=generated_at,
            )
        except Exception:
            logger.exception("Failed to render error HTML template")
            return None

    def _send_smtp(self, msg: MIMEText | MIMEMultipart) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=15) as server:
            server.ehlo()
            if self._port == 587:
                server.starttls()
                server.ehlo()
            if self._user and self._password:
                server.login(self._user, self._password)
            server.send_message(msg)

    def notify(self, opportunities: list[Opportunity]) -> None:
        if not self._enabled or not opportunities:
            return
        if not self._to or not self._from:
            logger.warning("Email not configured — skipping")
            return

        subject = f"Surge: {len(opportunities)} oportunidade(s) detectada(s)"
        body_lines = ["Surge detectou quedas relevantes:\n"]
        for opp in opportunities:
            body_lines.append(f"- {opp.summary()}")
        plain_text = "\n".join(body_lines)

        html_body = self.render_opportunities_html(opportunities)

        msg: MIMEText | MIMEMultipart
        if html_body:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = self._to
            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        else:
            msg = MIMEText(plain_text, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = self._to

        try:
            self._send_smtp(msg)
            logger.info("Email sent to %s (%d opportunities)", self._to, len(opportunities))
        except Exception:
            logger.exception("Failed to send email")
            raise

    def notify_error(self, message: str) -> None:
        if not self._enabled or not self._to or not self._from:
            return

        subject = "Surge: erro no scanner"
        html_body = self.render_error_html(message)

        msg: MIMEText | MIMEMultipart
        if html_body:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = self._to
            msg.attach(MIMEText(message, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        else:
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = self._to

        try:
            self._send_smtp(msg)
        except Exception:
            logger.exception("Failed to send error email")
