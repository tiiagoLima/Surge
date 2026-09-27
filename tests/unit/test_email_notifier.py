"""Unit tests for EmailNotifier with HTML template support."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from unittest.mock import patch

import pytest

from src.investments.adapters.outbound.email_notifier import EmailNotifier
from src.investments.domain.models import Opportunity, Quote


def _make_quote(ticker: str = "PETR4.SA", price: float = 28.40, prev: float = 31.20) -> Quote:
    return Quote(
        ticker=ticker,
        price=price,
        currency="BRL",
        timestamp=datetime.now(UTC),
        source="yfinance",
        previous_close=prev,
    )


def _make_opp(ticker: str = "PETR4.SA") -> Opportunity:
    q = _make_quote(ticker)
    drop = ((q.price - q.previous_close) / q.previous_close * 100) if q.previous_close else -5.0
    return Opportunity(quote=q, drop_pct=drop, threshold_pct=5.0, detected_at=datetime.now(UTC))


def _notifier(enabled: bool = True, templates_dir: str | Path | None = None) -> EmailNotifier:
    return EmailNotifier(
        smtp_host="smtp.test.local",
        smtp_port=587,
        smtp_user="user@test.com",
        smtp_password="secret",
        email_from="surge@test.com",
        email_to="dest@test.com",
        enabled=enabled,
        templates_dir=templates_dir,
    )


class TestEmailNotifierDisabled:
    def test_notify_disabled_does_nothing(self):
        n = _notifier(enabled=False)
        with patch.object(n, "_send_smtp") as mock_send:
            n.notify([_make_opp()])
            mock_send.assert_not_called()

    def test_notify_error_disabled_does_nothing(self):
        n = _notifier(enabled=False)
        with patch.object(n, "_send_smtp") as mock_send:
            n.notify_error("algo falhou")
            mock_send.assert_not_called()

    def test_notify_empty_list_does_nothing(self):
        n = _notifier(enabled=True)
        with patch.object(n, "_send_smtp") as mock_send:
            n.notify([])
            mock_send.assert_not_called()


class TestHTMLRendering:
    """Tests using the real templates directory."""

    @pytest.fixture
    def notifier_with_templates(self) -> EmailNotifier:
        templates_dir = (
            Path(__file__).resolve().parents[2] / "src" / "investments" / "assets" / "templates"
        )
        return _notifier(templates_dir=templates_dir)

    def test_render_opportunities_html_contains_ticker(self, notifier_with_templates):
        html = notifier_with_templates.render_opportunities_html([_make_opp("PETR4.SA")])
        assert html is not None
        assert "PETR4.SA" in html

    def test_render_opportunities_html_contains_drop_pct(self, notifier_with_templates):
        html = notifier_with_templates.render_opportunities_html([_make_opp()])
        assert html is not None
        # drop ≈ -8.97% -> badge must show at least "8"
        assert "8." in html

    def test_render_opportunities_html_multiple_tickers(self, notifier_with_templates):
        opps = [_make_opp("PETR4.SA"), _make_opp("VALE3.SA")]
        html = notifier_with_templates.render_opportunities_html(opps)
        assert html is not None
        assert "PETR4.SA" in html
        assert "VALE3.SA" in html

    def test_render_error_html_contains_message(self, notifier_with_templates):
        html = notifier_with_templates.render_error_html("Conexão recusada pelo servidor SMTP")
        assert html is not None
        assert "Conexão recusada pelo servidor SMTP" in html

    def test_render_returns_none_when_no_templates_dir(self):
        n = _notifier(templates_dir="/caminho/inexistente")
        assert n.render_opportunities_html([_make_opp()]) is None
        assert n.render_error_html("erro") is None


class TestNotifyHTMLMultipart:
    """Test that notify() builds MIMEMultipart when HTML is available."""

    @pytest.fixture
    def notifier_with_templates(self) -> EmailNotifier:
        templates_dir = (
            Path(__file__).resolve().parents[2] / "src" / "investments" / "assets" / "templates"
        )
        return _notifier(templates_dir=templates_dir)

    def test_notify_sends_multipart_with_html(self, notifier_with_templates):
        captured: list = []

        def capture(msg):
            captured.append(msg)

        notifier_with_templates._send_smtp = capture  # type: ignore[method-assign]
        notifier_with_templates.notify([_make_opp()])

        assert len(captured) == 1
        msg = captured[0]
        assert isinstance(msg, MIMEMultipart)
        content_types = [part.get_content_type() for part in msg.get_payload()]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    def test_notify_error_sends_multipart_with_html(self, notifier_with_templates):
        captured: list = []

        def capture(msg):
            captured.append(msg)

        notifier_with_templates._send_smtp = capture  # type: ignore[method-assign]
        notifier_with_templates.notify_error("falha crítica no sistema")

        assert len(captured) == 1
        msg = captured[0]
        assert isinstance(msg, MIMEMultipart)

    def test_notify_fallback_to_plain_on_render_failure(self, notifier_with_templates):
        captured: list = []

        def capture(msg):
            captured.append(msg)

        notifier_with_templates._send_smtp = capture  # type: ignore[method-assign]
        # Force render to fail
        notifier_with_templates.render_opportunities_html = lambda _: None  # type: ignore[method-assign]
        notifier_with_templates.notify([_make_opp()])

        assert len(captured) == 1
        from email.mime.text import MIMEText

        assert isinstance(captured[0], MIMEText)


class TestSMTPIntegration:
    """Test that _send_smtp is called on a real notify flow."""

    def test_notify_calls_send_smtp(self):
        n = _notifier(templates_dir="/no/templates")
        with patch.object(n, "_send_smtp") as mock_send:
            n.notify([_make_opp()])
            mock_send.assert_called_once()

    def test_notify_raises_on_smtp_error(self):
        n = _notifier(templates_dir="/no/templates")
        with (
            patch.object(n, "_send_smtp", side_effect=smtplib.SMTPException("timeout")),
            pytest.raises(smtplib.SMTPException),
        ):
            n.notify([_make_opp()])
