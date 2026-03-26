"""Tests for MCP tool handlers.

Tools are tested as plain functions — no real MCP server or transport needed.
All dependencies (MarketService, AIProvider) are mocked.
"""

from unittest.mock import MagicMock

import pytest

from src.mcp.tools import (
    handle_get_stocks_by_region,
    handle_get_top_movers,
    handle_search_symbol,
    handle_get_market_summary,
    handle_trigger_refresh,
)
from src.ai.base import MarketInsight


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STOCKS = [
    {"symbol": "AAPL.BA", "name": "Apple", "price": 150.0, "scraped_at": "2026-03-25T12:00:00"},
    {"symbol": "MSFT.BA", "name": "Microsoft", "price": 320.0, "scraped_at": "2026-03-25T12:00:00"},
]

INSIGHT = MarketInsight(
    summary="Market is neutral.",
    anomalies=[],
    trends={"direction": "neutral", "notable_movers": [], "confidence": "medium"},
    provider="LocalProvider",
    generated_at="2026-03-25T12:00:00",
)


@pytest.fixture
def service():
    svc = MagicMock()
    svc.get_stocks_by_region.return_value = {
        "region": "Argentina",
        "data": STOCKS,
        "freshness": "fresh",
        "last_scraped_at": "2026-03-25T12:00:00",
    }
    svc.get_top_movers.return_value = STOCKS
    svc.search_symbol.return_value = STOCKS
    svc.get_aggregated_for_ai.return_value = STOCKS
    return svc


@pytest.fixture
def ai_provider():
    provider = MagicMock()
    provider.analyze.return_value = INSIGHT
    return provider


# ---------------------------------------------------------------------------
# get_stocks_by_region
# ---------------------------------------------------------------------------

def test_get_stocks_returns_region_and_data(service, ai_provider):
    result = handle_get_stocks_by_region(service, "Argentina")
    assert result["region"] == "Argentina"
    assert "total_stocks" in result
    assert "sample_top10_by_price" in result


def test_get_stocks_includes_freshness(service, ai_provider):
    result = handle_get_stocks_by_region(service, "Argentina")
    assert "freshness" in result


def test_get_stocks_includes_last_scraped_at(service, ai_provider):
    result = handle_get_stocks_by_region(service, "Argentina")
    assert "last_scraped_at" in result


def test_get_stocks_calls_service(service, ai_provider):
    handle_get_stocks_by_region(service, "Belgium")
    service.get_stocks_by_region.assert_called_once_with("Belgium")


# ---------------------------------------------------------------------------
# get_top_movers
# ---------------------------------------------------------------------------

def test_get_top_movers_returns_region_and_movers(service, ai_provider):
    result = handle_get_top_movers(service, "Argentina", n=5)
    assert result["region"] == "Argentina"
    assert result["movers"] == STOCKS


def test_get_top_movers_passes_n_to_service(service, ai_provider):
    handle_get_top_movers(service, "Argentina", n=3)
    service.get_top_movers.assert_called_once_with("Argentina", 3, "price")


# ---------------------------------------------------------------------------
# search_symbol
# ---------------------------------------------------------------------------

def test_search_symbol_returns_results(service, ai_provider):
    result = handle_search_symbol(service, "AAPL")
    assert result["symbol"] == "AAPL"
    assert result["results"] == STOCKS


def test_search_symbol_calls_service(service, ai_provider):
    handle_search_symbol(service, "MSFT")
    service.search_symbol.assert_called_once_with("MSFT")


def test_search_symbol_returns_empty_list_when_no_match(service, ai_provider):
    service.search_symbol.return_value = []
    result = handle_search_symbol(service, "ZZZZ")
    assert result["results"] == []


# ---------------------------------------------------------------------------
# get_market_summary
# ---------------------------------------------------------------------------

def test_get_market_summary_returns_insight_fields(service, ai_provider):
    result = handle_get_market_summary(service, ai_provider, "Argentina")
    assert result["summary"] == INSIGHT.summary
    assert result["provider"] == INSIGHT.provider
    assert "anomalies" in result
    assert "trends" in result


def test_get_market_summary_calls_get_aggregated_for_ai(service, ai_provider):
    handle_get_market_summary(service, ai_provider, "Argentina")
    service.get_aggregated_for_ai.assert_called_once_with("Argentina")


def test_get_market_summary_calls_ai_provider_analyze(service, ai_provider):
    handle_get_market_summary(service, ai_provider, "Argentina")
    ai_provider.analyze.assert_called_once_with(STOCKS)


# ---------------------------------------------------------------------------
# trigger_refresh
# ---------------------------------------------------------------------------

def test_trigger_refresh_returns_queued_true_when_submitted(service, ai_provider):
    service.trigger_refresh.return_value = True
    result = handle_trigger_refresh(service, "Argentina")
    assert result["queued"] is True
    assert result["region"] == "Argentina"


def test_trigger_refresh_returns_queued_false_for_duplicate(service, ai_provider):
    service.trigger_refresh.return_value = False
    result = handle_trigger_refresh(service, "Argentina")
    assert result["queued"] is False


def test_trigger_refresh_includes_message(service, ai_provider):
    service.trigger_refresh.return_value = True
    result = handle_trigger_refresh(service, "Argentina")
    assert "message" in result
