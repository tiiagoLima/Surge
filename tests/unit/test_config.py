"""Unit tests for config parsing."""

from src.shared.config import Settings


def test_drop_threshold_default():
    s = Settings()  # type: ignore[call-arg]
    assert s.drop_threshold == 5.0


def test_no_hardcoded_watchlist():
    """SURGE_WATCHLIST foi removido — carteira vive no SQLite via PortfolioPort."""
    s = Settings()  # type: ignore[call-arg]
    assert not hasattr(s, "watchlist")
    assert not hasattr(s, "tickers")
