"""SQLite storage — StoragePort implementation."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.investments.domain.models import Holding, Opportunity, Quote
from src.investments.domain.ports import PortfolioPort, StoragePort

logger = logging.getLogger(__name__)


class SqliteRepository(PortfolioPort, StoragePort):
    """Persists quotes, opportunities and holdings in SQLite.

    Implements StoragePort and PortfolioPort separately (ISP) —
    same SQLite file, isolated interfaces.
    """

    def __init__(
        self, db_path: str | Path = "./surge.db", connection: sqlite3.Connection | None = None
    ) -> None:
        if db_path == ":memory:" and connection is None:
            raise ValueError("Use create_memory_database and pass its connection explicitly")
        # Schema provisioning is explicit; this adapter only performs DML.
        self._db_path = Path(db_path).expanduser().resolve()
        self._connection = connection
        self._is_memory = connection is not None

    def _connect(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        if self._is_memory:
            # return a new connection to same shared memory URI
            conn = sqlite3.connect(str(self._db_path), uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            return conn
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def save_quote(self, quote: Quote) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO quotes "
                "(ticker, price, currency, timestamp, source, previous_close) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    quote.ticker,
                    quote.price,
                    quote.currency,
                    quote.timestamp.isoformat(),
                    quote.source,
                    quote.previous_close,
                ),
            )
            conn.commit()

    def get_last_quote(self, ticker: str) -> Quote | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM quotes WHERE ticker = ? ORDER BY timestamp DESC LIMIT 1",
                (ticker.upper(),),
            ).fetchone()
            if row is None:
                return None
            return Quote(
                ticker=row["ticker"],
                price=row["price"],
                currency=row["currency"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                source=row["source"],
                previous_close=row["previous_close"],
            )

    def save_opportunity(self, opportunity: Opportunity) -> None:
        q = opportunity.quote
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO opportunities
                   (ticker, price, currency, timestamp, source,
                    previous_close, drop_pct, threshold_pct, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    q.ticker,
                    q.price,
                    q.currency,
                    q.timestamp.isoformat(),
                    q.source,
                    q.previous_close,
                    opportunity.drop_pct,
                    opportunity.threshold_pct,
                    opportunity.detected_at.isoformat(),
                ),
            )
            conn.commit()

    def get_recent_opportunities(self, limit: int = 20) -> list[Opportunity]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM opportunities ORDER BY detected_at DESC LIMIT ?", (limit,)
            ).fetchall()
            result: list[Opportunity] = []
            for row in rows:
                quote = Quote(
                    ticker=row["ticker"],
                    price=row["price"],
                    currency=row["currency"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    source=row["source"],
                    previous_close=row["previous_close"],
                )
                result.append(
                    Opportunity(
                        quote=quote,
                        drop_pct=row["drop_pct"],
                        threshold_pct=row["threshold_pct"],
                        detected_at=datetime.fromisoformat(row["detected_at"]),
                    )
                )
            return result

    # --- PortfolioPort ---

    def save_holding(self, holding: Holding) -> None:
        """Upsert holding by ticker (ticker normalized to upper)."""
        added_at = (holding.added_at or datetime.now()).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO holdings "
                "(ticker, quantity, avg_price, currency, added_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    holding.ticker.upper(),
                    float(holding.quantity),
                    float(holding.avg_price) if holding.avg_price is not None else None,
                    holding.currency.upper(),
                    added_at,
                ),
            )
            conn.commit()

    def remove_holding(self, ticker: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))
            conn.commit()
            return cur.rowcount > 0

    def get_holding(self, ticker: str) -> Holding | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM holdings WHERE ticker = ?", (ticker.upper(),)
            ).fetchone()
            if row is None:
                return None
            return Holding(
                ticker=row["ticker"],
                quantity=row["quantity"],
                avg_price=row["avg_price"],
                currency=row["currency"],
                added_at=datetime.fromisoformat(row["added_at"]),
            )

    def list_holdings(self) -> list[Holding]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM holdings ORDER BY ticker").fetchall()
            return [
                Holding(
                    ticker=row["ticker"],
                    quantity=row["quantity"],
                    avg_price=row["avg_price"],
                    currency=row["currency"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                )
                for row in rows
            ]
