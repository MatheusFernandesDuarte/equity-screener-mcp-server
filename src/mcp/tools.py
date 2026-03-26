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
    """Return a compact summary for a region (freshness + count + top 10 sample).
    Triggers background refresh if stale. Does NOT return the full stock list —
    use get_top_movers to get ranked results."""
    response = service.get_stocks_by_region(region)
    data = response["data"]
    result = {
        "region": response["region"],
        "freshness": response["freshness"],
        "last_scraped_at": response["last_scraped_at"],
        "total_stocks": len(data),
        "sample_top10_by_price": data[:10],
    }
    if response["freshness"] == "expired" and not data:
        result["message"] = (
            f"No data found for '{region}'. A scrape has been queued — "
            "run this tool again in ~2 minutes once the data is ready."
        )
    return result


def handle_get_top_movers(
    service: MarketService, region: str, n: int = 10, sort_by: str = "price"
) -> dict:
    """Return top N stocks sorted by price or change_pct from the latest snapshot."""
    return {
        "region": region,
        "sort_by": sort_by,
        "movers": service.get_top_movers(region, n, sort_by),
    }


def handle_search_symbol(service: MarketService, symbol: str) -> dict:
    """Search for a symbol (case-insensitive partial match) across all regions."""
    return {
        "symbol": symbol,
        "results": service.search_symbol(symbol),
    }


def handle_get_market_summary(service: MarketService, ai_provider: AIProvider, region: str) -> dict:
    """Generate an AI-powered summary for a region using pre-aggregated data."""
    # Ensure freshness check + background refresh is triggered
    service.get_stocks_by_region(region)

    data = service.get_aggregated_for_ai(region)
    if not data:
        return {
            "region": region,
            "summary": "No data available yet.",
            "anomalies": [],
            "trends": [],
            "provider": "none",
            "generated_at": None,
            "message": (
                f"No data found for '{region}'. A scrape has been queued — "
                "ask again in ~2 minutes once the data is ready."
            ),
        }

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
    queued = service.trigger_refresh(region)
    return {
        "region": region,
        "queued": queued,
        "message": (
            f"Scrape queued for '{region}'." if queued else f"'{region}' is already being scraped."
        ),
    }


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------


def register_tools(mcp, service: MarketService, ai_provider: AIProvider) -> None:
    """Register all tool handlers with a FastMCP instance."""

    @mcp.tool()
    def get_stocks_by_region(region: str) -> dict:
        """Return cached stocks for a region along with freshness metadata.

        Always check the 'freshness' field in the response:
        - 'fresh': data is recent, use it directly.
        - 'stale': data exists but is aging — use it and mention it may be slightly outdated.
        - 'expired': data is too old or missing. Call trigger_refresh(region) immediately,
          inform the user that a scrape is running, and suggest they ask again in ~2 minutes.
        """
        return handle_get_stocks_by_region(service, region)

    @mcp.tool()
    def get_top_movers(region: str, n: int = 10, sort_by: str = "price") -> dict:
        """Return top N stocks for a region, sorted by 'price' or 'change_pct'.

        Use sort_by='change_pct' for questions like 'qual ação mais subiu/caiu hoje'.
        Use sort_by='price' (default) for 'ações mais caras / top por valor'.
        Before using results, check freshness via get_stocks_by_region(region).
        If freshness is 'expired', call trigger_refresh(region) first.
        """
        return handle_get_top_movers(service, region, n, sort_by)

    @mcp.tool()
    def search_symbol(symbol: str) -> dict:
        """Search for a symbol (case-insensitive, partial match) across all scraped regions."""
        return handle_search_symbol(service, symbol)

    @mcp.tool()
    def get_market_summary(region: str) -> dict:
        """Generate an AI-powered market summary with anomaly detection and trends.

        This tool checks freshness automatically. If the data is expired or missing,
        it queues a background scrape and returns a message asking the user to retry.
        For time-sensitive questions (e.g. 'today', 'right now'), also verify
        'last_scraped_at' in the response and warn the user if data is older than 1 hour.
        """
        return handle_get_market_summary(service, ai_provider, region)

    @mcp.tool()
    def trigger_refresh(region: str) -> dict:
        """Queue a background scrape for a region to fetch fresh data from Yahoo Finance.

        Call this when freshness is 'expired' or when the user explicitly asks for
        up-to-date data. The scrape runs in the background — data will be ready
        in approximately 1-3 minutes depending on region size.
        """
        return handle_trigger_refresh(service, region)
