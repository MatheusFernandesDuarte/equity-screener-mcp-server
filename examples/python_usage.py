"""
Python API usage examples — querying the service layer directly.

Run: uv run python examples/python_usage.py
(Requires at least one region to have been scraped first via run.py)
"""

from src.ai.factory import get_provider
from src.app.factories import create_engine_factory
from src.scraper.manager import ScrapeManager
from src.services.market_service import MarketService
from src.storage.database import get_connection
from src.storage.repository import StockRepository


def build_service() -> tuple[MarketService, ScrapeManager]:
    conn = get_connection()
    repo = StockRepository(conn)
    manager = ScrapeManager(engine_factory=create_engine_factory(), repository=repo)
    service = MarketService(repository=repo, scrape_manager=manager)
    return service, manager


def main():
    service, manager = build_service()
    ai = get_provider()

    # --- Get stocks for a region (served from cache, refresh triggered if stale) ---
    response = service.get_stocks_by_region("Belgium")
    print(f"Region:    {response['region']}")
    print(f"Freshness: {response['freshness']}")
    print(f"Stocks:    {len(response['data'])} rows")
    print()

    # --- Top movers ---
    movers = service.get_top_movers("Belgium", n=5)
    print("Top 5 movers:")
    for m in movers:
        print(f"  {m['symbol']:12s} {m['name'][:30]:30s} {m['price']:.2f}")
    print()

    # --- Symbol search ---
    results = service.search_symbol("ABI")
    print(f"Search 'ABI': {len(results)} results")
    for r in results:
        print(f"  [{r['region']}] {r['symbol']} — {r['price']:.2f}")
    print()

    # --- AI summary ---
    data = service.get_aggregated_for_ai("Belgium", limit=20)
    if data:
        insight = ai.analyze(data)
        print(f"AI summary ({insight.provider}):")
        print(f"  {insight.summary}")
        print(f"  Anomalies: {len(insight.anomalies)}")
        print(f"  Trend: {insight.trends.get('direction', 'unknown')}")
    print()

    # --- Manually trigger a background refresh ---
    queued = manager.submit("Argentina")
    print(f"Refresh queued for Argentina: {queued}")

    manager.shutdown()


if __name__ == "__main__":
    main()
