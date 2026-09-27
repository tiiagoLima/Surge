"""Email input models and investment command parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class IncomingEmail:
    """Email received by an inbound adapter."""

    uid: str
    subject: str
    body: str


@dataclass(frozen=True)
class InvestmentPurchase:
    """Purchase extracted from a Surge investment email."""

    ticker: str
    quantity: float
    unit_price: float
    currency: str
    purchase_date: date


class InvestmentEmailParser:
    """Parses the supported Portuguese investment email format."""

    _PATTERN = re.compile(
        r"(?P<verb>comprei|compramos)\s+(?P<quantity>[\d.,]+)\s+"
        r"(?:cotas?|ações?|unidades?)\s+(?:do ativo\s+|de\s+)?"
        r"(?P<ticker>[A-Za-z0-9.\-]+)\s+(?:cada\s+)?"
        r"(?:cota|ação|unidade)?\s*(?:por|a)\s+"
        r"(?P<currency>R\$|US\$|USD|BRL|EUR|€)?\s*"
        r"(?P<price>[\d.,]+)",
        re.IGNORECASE,
    )

    def parse(self, body: str, received_at: date | None = None) -> InvestmentPurchase:
        """Parse a purchase from an email body.

        Raises:
            ValueError: If the body does not match the supported format.
        """
        match = self._PATTERN.search(" ".join(body.split()))
        if match is None:
            raise ValueError("formato inválido; use: Hoje comprei 10 cotas de PETR4 por R$ 30,00")

        quantity = self._number(match.group("quantity"))
        price = self._number(match.group("price"))
        if quantity <= 0 or price <= 0:
            raise ValueError("quantidade e preço devem ser maiores que zero")

        return InvestmentPurchase(
            ticker=match.group("ticker").upper(),
            quantity=quantity,
            unit_price=price,
            currency=self._currency(match.group("currency")),
            purchase_date=self._parse_date(body, received_at or date.today()),
        )

    @staticmethod
    def _number(value: str) -> float:
        normalized = value.strip().replace(".", "").replace(",", ".")
        if value.count(".") == 1 and value.count(",") == 0:
            normalized = value
        return float(normalized)

    @staticmethod
    def _currency(value: str | None) -> str:
        return {"R$": "BRL", "US$": "USD", "€": "EUR"}.get(value or "R$", value or "BRL")

    @staticmethod
    def _parse_date(body: str, fallback: date) -> date:
        match = re.search(r"(?:dia\s+)?(\d{1,2})/(\d{1,2})/(\d{2,4})", body)
        if match is None:
            return fallback
        year = int(match.group(3))
        if year < 100:
            year += 2000
        return datetime(year, int(match.group(2)), int(match.group(1))).date()
