from datetime import date

import pytest

from src.investments.domain.email_models import InvestmentEmailParser


def test_parser_extracts_purchase():
    purchase = InvestmentEmailParser().parse(
        "Hoje comprei 10 cotas de PETR4 por R$ 30,00", received_at=date(2026, 9, 26)
    )
    assert purchase.ticker == "PETR4"
    assert purchase.quantity == 10
    assert purchase.unit_price == 30
    assert purchase.currency == "BRL"
    assert purchase.purchase_date == date(2026, 9, 26)


def test_parser_extracts_explicit_date_and_decimal_quantity():
    purchase = InvestmentEmailParser().parse(
        "Comprei 1,5 cotas de AAPL por US$ 180.25 em 25/09/2026"
    )
    assert purchase.quantity == 1.5
    assert purchase.unit_price == 180.25
    assert purchase.currency == "USD"
    assert purchase.purchase_date == date(2026, 9, 25)


def test_parser_rejects_invalid_message():
    with pytest.raises(ValueError, match="formato inválido"):
        InvestmentEmailParser().parse("Olá Surge, tudo bem?")
