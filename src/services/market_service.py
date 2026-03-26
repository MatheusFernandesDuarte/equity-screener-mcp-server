"""MarketService — the single data interface for all consumers (MCP, CLI, AI).

Reads always come from DuckDB.
Scraping is always triggered in the background via ScrapeManager.
This layer never touches Selenium directly.
"""

from datetime import datetime, timezone
from enum import Enum

from src.scraper.manager import ScrapeManager
from src.storage.repository import StockRepository


class Freshness(Enum):
    FRESH   = "fresh"    # now < last_scraped + TTL
    STALE   = "stale"    # TTL < now < 2×TTL  → serve + background refresh
    EXPIRED = "expired"  # now > 2×TTL         → serve + mark critical


class MarketService:
    """Orchestrates cache reads, freshness decisions, and background refresh triggers."""

    def __init__(self, repository: StockRepository, scrape_manager: ScrapeManager) -> None:
        self._repo = repository
        self._manager = scrape_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_stocks_by_region(self, region: str) -> dict:
        """Return latest cached stocks for a region. Triggers background refresh if stale."""
        data = self._repo.get_latest_by_region(region)
        meta = self._repo.get_region_metadata(region)

        self._repo.increment_access_count(region)
        self._maybe_update_ttl(region, meta)

        freshness = self._compute_freshness(meta)

        if freshness in (Freshness.STALE, Freshness.EXPIRED):
            self._manager.submit(region)

        return {
            "region": region,
            "data": data,
            "freshness": freshness.value,
            "last_scraped_at": meta["last_scraped_at"] if meta else None,
        }

    def get_top_movers(self, region: str, n: int = 10, sort_by: str = "price") -> list[dict]:
        return self._repo.get_top_movers(region, n, sort_by)

    def search_symbol(self, symbol: str) -> list[dict]:
        return self._repo.search_symbol(symbol)

    def get_aggregated_for_ai(self, region: str, limit: int = 50) -> list[dict]:
        """Return pre-sliced, pre-ranked data for the AI layer (max rows, last 24h)."""
        return self._repo.get_aggregated_for_ai(region, limit)

    def trigger_refresh(self, region: str) -> bool:
        """Queue a background scrape for a region. Returns True if queued, False if already in progress."""
        return self._manager.submit(region)

    # ------------------------------------------------------------------
    # Freshness
    # ------------------------------------------------------------------

    def _compute_freshness(self, meta: dict | None) -> Freshness:
        if not meta or not meta.get("last_scraped_at"):
            return Freshness.EXPIRED

        last = datetime.fromisoformat(meta["last_scraped_at"])
        ttl = meta["ttl_seconds"]
        age = (datetime.utcnow() - last).total_seconds()

        if age < ttl:
            return Freshness.FRESH
        if age < ttl * 2:
            return Freshness.STALE
        return Freshness.EXPIRED

    # ------------------------------------------------------------------
    # Dynamic TTL
    # ------------------------------------------------------------------

    def _compute_ttl(self, access_count: int) -> int:
        if access_count > 50:
            return 3_600
        if access_count > 10:
            return 7_200
        return 14_400

    def _maybe_update_ttl(self, region: str, meta: dict | None) -> None:
        """Recompute and persist TTL if it changed based on new access count."""
        if not meta or not meta.get("last_scraped_at"):
            return
        new_ttl = self._compute_ttl(meta["access_count"] + 1)
        if new_ttl != meta["ttl_seconds"]:
            self._repo.upsert_region_metadata(
                region,
                datetime.fromisoformat(meta["last_scraped_at"]),
                ttl_seconds=new_ttl,
            )
