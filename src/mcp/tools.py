"""MCP tool handler functions — transport-agnostic, fully testable.

Each handle_* function takes explicit dependencies so they can be tested
without a running MCP server. register_tools() wires them into FastMCP.
"""

from src.ai.base import AIProvider
from src.services.market_service import MarketService


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------

def handle_get_stocks_by_region(service: MarketService, region: str) -> dict:
    """Return latest cached stocks for a region. Triggers background refresh if stale."""
    response = service.get_stocks_by_region(region)
    return {
        "region": response["region"],
        "stocks": response["data"],
        "freshness": response["freshness"],
        "last_scraped_at": response["last_scraped_at"],
    }


def handle_get_top_movers(service: MarketService, region: str, n: int = 10) -> dict:
    """Return top N stocks by price from the latest snapshot for a region."""
    return {
        "region": region,
        "movers": service.get_top_movers(region, n),
    }


def handle_search_symbol(service: MarketService, symbol: str) -> dict:
    """Search for a symbol (case-insensitive partial match) across all regions."""
    return {
        "symbol": symbol,
        "results": service.search_symbol(symbol),
    }


def handle_get_market_summary(
    service: MarketService, ai_provider: AIProvider, region: str
) -> dict:
    """Generate an AI-powered summary for a region using pre-aggregated data."""
    data = service.get_aggregated_for_ai(region)
    insight = ai_provider.analyze(data)
    return {
        "region": region,
        "summary": insight.summary,
        "anomalies": insight.anomalies,
        "trends": insight.trends,
        "provider": insight.provider,
        "generated_at": insight.generated_at,
    }


def handle_trigger_refresh(service: MarketService, region: str) -> dict:
    """Manually queue a background scrape for a region."""
    queued = service.scrape_manager.submit(region)
    return {
        "region": region,
        "queued": queued,
        "message": (
            f"Scrape queued for '{region}'."
            if queued
            else f"'{region}' is already being scraped."
        ),
    }


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register_tools(mcp, service: MarketService, ai_provider: AIProvider) -> None:
    """Register all tool handlers with a FastMCP instance."""

    @mcp.tool()
    def get_stocks_by_region(region: str) -> dict:
        """Return latest cached stocks for a region."""
        return handle_get_stocks_by_region(service, region)

    @mcp.tool()
    def get_top_movers(region: str, n: int = 10) -> dict:
        """Return top N stocks by price for a region."""
        return handle_get_top_movers(service, region, n)

    @mcp.tool()
    def search_symbol(symbol: str) -> dict:
        """Search for a symbol across all scraped regions."""
        return handle_search_symbol(service, symbol)

    @mcp.tool()
    def get_market_summary(region: str) -> dict:
        """Generate an AI-powered market summary for a region."""
        return handle_get_market_summary(service, ai_provider, region)

    @mcp.tool()
    def trigger_refresh(region: str) -> dict:
        """Manually queue a background scrape for a region."""
        return handle_trigger_refresh(service, region)
