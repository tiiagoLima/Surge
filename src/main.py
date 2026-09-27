"""Composition root — Surge.

Wires adapters into use cases. No business logic here.
Inbound adapter (CLI) is agnostic — same use cases can be called by Telegram later.
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.investments.adapters.inbound.imap_inbox_adapter import ImapInboxAdapter
from src.investments.adapters.inbound.scheduler_trigger import SchedulerTrigger
from src.investments.adapters.outbound.brapi_adapter import BrapiAdapter
from src.investments.adapters.outbound.composite_notifier import CompositeNotifier
from src.investments.adapters.outbound.composite_quote_adapter import CompositeQuoteAdapter
from src.investments.adapters.outbound.email_notifier import EmailNotifier
from src.investments.adapters.outbound.sqlite_repository import SqliteRepository
from src.investments.adapters.outbound.telegram_notifier import TelegramNotifier
from src.investments.adapters.outbound.yfinance_adapter import YFinanceAdapter
from src.investments.application.manage_portfolio_use_case import ManagePortfolioUseCase
from src.investments.application.market_radar_use_case import MarketRadarUseCase
from src.investments.application.process_investment_emails_use_case import (
    ProcessInvestmentEmailsUseCase,
)
from src.investments.application.scan_portfolio_use_case import ScanPortfolioUseCase
from src.memory.adapters.outbound.fake_semantic_memory import FakeSemanticMemoryAdapter
from src.memory.application.save_preference_use_case import SavePreferenceUseCase
from src.memory.application.search_semantic_memory_use_case import SearchSemanticMemoryUseCase
from src.shared.config import get_settings

logger = logging.getLogger(__name__)


def _build_ports():
    """Build all adapters. Returns ports tuple."""
    settings = get_settings()
    yf = YFinanceAdapter()
    brapi = BrapiAdapter(base_url=settings.brapi_base_url, token=settings.brapi_token or None)
    quote_port = CompositeQuoteAdapter(primary=yf, fallback=brapi)
    # SqliteRepository implements StoragePort and PortfolioPort (ISP)
    repo = SqliteRepository(db_path=settings.db_path)

    notifiers = []
    if settings.email_enabled:
        notifiers.append(
            EmailNotifier(
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                smtp_user=settings.smtp_user,
                smtp_password=settings.smtp_password,
                email_from=settings.email_from,
                email_to=settings.email_to,
                enabled=True,
            )
        )
    if settings.telegram_enabled:
        notifiers.append(
            TelegramNotifier(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                enabled=True,
            )
        )
    if not notifiers:
        notifiers.append(EmailNotifier("", 0, "", "", "", "", enabled=False))

    notification_port = CompositeNotifier(notifiers)
    return settings, repo, quote_port, notification_port, repo


def build_save_preference_use_case() -> SavePreferenceUseCase:
    """Build the semantic-memory preference use case."""
    return SavePreferenceUseCase(memory_port=FakeSemanticMemoryAdapter())


def build_search_semantic_memory_use_case() -> SearchSemanticMemoryUseCase:
    """Build the semantic-memory search use case."""
    return SearchSemanticMemoryUseCase(memory_port=FakeSemanticMemoryAdapter())


def build_manage_portfolio_use_case() -> ManagePortfolioUseCase:
    _, portfolio_port, quote_port, _, _ = _build_ports()
    return ManagePortfolioUseCase(portfolio_port=portfolio_port, quote_port=quote_port)


def build_scan_portfolio_use_case() -> ScanPortfolioUseCase:
    settings, portfolio_port, quote_port, notification_port, storage_port = _build_ports()
    return ScanPortfolioUseCase(
        portfolio_port=portfolio_port,
        quote_port=quote_port,
        notification_port=notification_port,
        storage_port=storage_port,
        drop_threshold_pct=settings.drop_threshold,
    )


def build_market_radar_use_case() -> MarketRadarUseCase:
    settings, portfolio_port, quote_port, notification_port, storage_port = _build_ports()
    return MarketRadarUseCase(
        portfolio_port=portfolio_port,
        market_quote_port=quote_port,
        notification_port=notification_port,
        storage_port=storage_port,
        drop_threshold_pct=settings.drop_threshold,
    )


def run_scheduler() -> None:
    """Run with APScheduler (blocking) — imports emails and scans daily."""
    settings = get_settings()
    scan_portfolio = build_scan_portfolio_use_case()
    radar = build_market_radar_use_case()
    email_processor = None
    if settings.imap_enabled:
        _, portfolio_port, quote_port, _, _ = _build_ports()
        inbox = ImapInboxAdapter(
            host=settings.imap_host,
            port=settings.imap_port,
            username=settings.imap_user,
            password=settings.imap_password,
            mailbox=settings.imap_mailbox,
        )
        email_processor = ProcessInvestmentEmailsUseCase(
            inbox_port=inbox,
            portfolio_port=portfolio_port,
            quote_port=quote_port,
            subject_prefix=settings.investment_email_subject,
        )

    def process_emails() -> None:
        if email_processor is None:
            return
        try:
            count = email_processor.execute()
            logger.info("Processed %d investment emails", count)
        except Exception:
            logger.exception("Investment email processing failed")

    def job() -> None:
        process_emails()
        logger.info("Surge scheduled scan triggered")
        try:
            opps_p = scan_portfolio.execute()
            logger.info("Scheduled portfolio scan: %d opps", len(opps_p))
        except Exception:
            logger.exception("Scheduled portfolio scan failed")
        try:
            opps_r = radar.execute()
            logger.info("Scheduled radar scan: %d opps", len(opps_r))
        except Exception:
            logger.exception("Scheduled radar scan failed")

    logger.info("Surge starting — running initial scheduled scan")
    job()

    trigger = SchedulerTrigger(timezone=settings.timezone)
    trigger.schedule_daily(job, hour=settings.cron_hour, minute=settings.cron_minute)
    if email_processor is not None:
        trigger.schedule_interval(process_emails, minutes=settings.email_poll_minutes)
    trigger.start()


def main() -> None:
    parser = argparse.ArgumentParser(prog="surge", description="Surge — Personal Automation Hub")
    parser.add_argument(
        "--log-level", default=None, help="Override log level (DEBUG, INFO, WARNING)"
    )

    subparsers = parser.add_subparsers(dest="command")

    # portfolio subcommand
    p_parser = subparsers.add_parser(
        "portfolio", help="Manage holdings (agnostic — CLI is just inbound adapter)"
    )
    p_sub = p_parser.add_subparsers(dest="portfolio_cmd", required=True)
    p_add = p_sub.add_parser("add", help="Add holding (validates via Brapi)")
    p_add.add_argument("ticker", help="Ticker e.g. PETR4.SA")
    p_add.add_argument("--qty", type=float, required=True, help="Quantity")
    p_add.add_argument("--avg", type=float, default=None, help="Average price")
    p_add.add_argument("--currency", default="BRL", help="Currency (default BRL)")
    p_sub.add_parser("list", help="List holdings")
    p_rm = p_sub.add_parser("remove", help="Remove holding")
    p_rm.add_argument("ticker", help="Ticker")
    p_get = p_sub.add_parser("get", help="Show holding")
    p_get.add_argument("ticker", help="Ticker")

    # scan subcommand (single run; scheduler vive no modo sem subcomando)
    s_parser = subparsers.add_parser("scan", help="Run scans")
    s_parser.add_argument("--portfolio", action="store_true", help="Scan portfolio holdings")
    s_parser.add_argument(
        "--radar", action="store_true", help="Scan market radar (Brapi list, excludes holdings)"
    )

    # test-email subcommand
    e_parser = subparsers.add_parser("test-email", help="Test or preview email HTML template")
    e_parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate preview HTML file and open in default browser",
    )
    e_parser.add_argument(
        "--send",
        action="store_true",
        help="Send a test email using configured SMTP credentials",
    )

    args = parser.parse_args()

    settings = get_settings()
    level = (args.log_level or settings.log_level).upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    # No subcommand -> scheduler (portfolio + radar diários)
    if args.command is None:
        print("Surge -- Personal Automation Hub")
        holdings_preview = build_manage_portfolio_use_case().list()
        watch = [h.ticker for h in holdings_preview] or "(vazia)"
        print(f"   holdings={watch} threshold={settings.drop_threshold}%")
        run_scheduler()
        return

    if args.command == "portfolio":
        uc = build_manage_portfolio_use_case()
        if args.portfolio_cmd == "add":
            try:
                h = uc.add(
                    args.ticker, quantity=args.qty, avg_price=args.avg, currency=args.currency
                )
                print(
                    f"Holding adicionado: {h.ticker} "
                    f"qty={h.quantity} avg={h.avg_price} {h.currency}"
                )
            except ValueError as e:
                print(f"Erro: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.portfolio_cmd == "list":
            holdings = uc.list()
            if not holdings:
                print("Carteira vazia. Use 'surge portfolio add TICKER --qty N'")
            else:
                for h in holdings:
                    avg = f" avg={h.avg_price:.2f}" if h.avg_price is not None else ""
                    print(
                        f"{h.ticker:12} qty={h.quantity:g}{avg} {h.currency} (desde {h.added_at})"
                    )
        elif args.portfolio_cmd == "remove":
            removed = uc.remove(args.ticker)
            if removed:
                print(f"Removido {args.ticker.upper()}")
            else:
                print(f"Ticker não encontrado: {args.ticker}", file=sys.stderr)
                sys.exit(1)
        elif args.portfolio_cmd == "get":
            holding = uc.get(args.ticker)
            if holding is None:
                print(f"Não encontrado: {args.ticker}", file=sys.stderr)
                sys.exit(1)
            print(
                f"{holding.ticker} qty={holding.quantity} avg={holding.avg_price} "
                f"{holding.currency} added={holding.added_at}"
            )
        return

    if args.command == "scan":
        # default if no flag: run both
        do_portfolio = args.portfolio or not args.radar
        do_radar = args.radar or not args.portfolio
        # Actually if neither flagged, run both. If one flagged, run only that.
        if not args.portfolio and not args.radar:
            do_portfolio = do_radar = True
        if do_portfolio:
            print("Scanning portfolio...")
            scan_use_case = build_scan_portfolio_use_case()
            opps = scan_use_case.execute()
            print(f"Portfolio: {len(opps)} oportunidades")
            for o in opps:
                print(f"  - {o.summary()}")
        if do_radar:
            print("Scanning market radar (Brapi)...")
            radar_use_case = build_market_radar_use_case()
            opps = radar_use_case.execute()
            print(f"Radar: {len(opps)} oportunidades")
            for o in opps:
                print(f"  - {o.summary()}")
        return

    if args.command == "test-email":
        _cmd_test_email(args)
        return


def _make_fake_opportunities() -> list:
    """Generate synthetic opportunities for preview/test purposes."""
    from datetime import UTC, datetime

    from src.investments.domain.models import Opportunity, Quote

    now = datetime.now(UTC)
    quotes = [
        Quote(
            ticker="PETR4.SA",
            price=28.40,
            currency="BRL",
            timestamp=now,
            source="yfinance",
            previous_close=31.20,
        ),
        Quote(
            ticker="VALE3.SA",
            price=54.10,
            currency="BRL",
            timestamp=now,
            source="brapi",
            previous_close=58.90,
        ),
    ]
    return [
        Opportunity(
            quote=q,
            drop_pct=((q.price - (q.previous_close or q.price)) / (q.previous_close or q.price))
            * 100,
            threshold_pct=5.0,
            detected_at=now,
        )
        for q in quotes
    ]


def _cmd_test_email(args: argparse.Namespace) -> None:
    """Handle the test-email command (--preview or --send)."""
    import tempfile
    import webbrowser

    settings = get_settings()

    from src.investments.adapters.outbound.composite_notifier import CompositeNotifier
    from src.investments.adapters.outbound.email_notifier import EmailNotifier

    _, _, _, notification_port, _ = _build_ports()

    email_notifier: EmailNotifier | None = None
    if isinstance(notification_port, CompositeNotifier):
        for n in notification_port._notifiers:
            if isinstance(n, EmailNotifier) and n._enabled:
                email_notifier = n
                break

    if email_notifier is None:
        email_notifier = EmailNotifier(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            email_from=settings.email_from,
            email_to=settings.email_to,
            enabled=False,
        )

    opps = _make_fake_opportunities()

    if not args.preview and not args.send:
        print("Use --preview para visualizar no navegador ou --send para enviar o e-mail de teste.")
        return

    if args.preview:
        html = email_notifier.render_opportunities_html(opps)
        if not html:
            print("Erro: template HTML não encontrado em src/investments/assets/templates/")
            return
        with tempfile.NamedTemporaryFile(
            suffix="_surge_email_preview.html",
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as f:
            f.write(html)
            path = f.name
        print(f"Preview gerado em: {path}")
        webbrowser.open(f"file://{path}")

    if args.send:
        if not settings.email_enabled:
            print(
                "Aviso: SURGE_EMAIL_ENABLED=false — ativando modo de envio forçado para teste.",
                flush=True,
            )
        test_notifier = EmailNotifier(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            email_from=settings.email_from,
            email_to=settings.email_to,
            enabled=True,
        )
        print(f"Enviando e-mail de teste para {settings.email_to}...")
        try:
            test_notifier.notify(opps)
            print("E-mail de teste enviado com sucesso.")
        except Exception as e:
            print(f"Falha ao enviar: {e}")


if __name__ == "__main__":
    main()
